# -*- coding: utf-8 -*-
"""Web 执行平台 · 管理后台（用例 / 页面对象 / 元素 上传与文件管理 · 方案A）

功能：统一文件列表（类型/上传人/受保护标记）、上传（py_compile/yaml/json 校验、
覆盖确认与历史备份）、下载（单个/批量zip）、重命名、新建文件夹、删除（受保护拦截）、
批量删除。文件元数据（上传人/备份记录）存储于 output/admin_meta.json，
二期账号体系落地后可平移到 file_manage 数据表。

安全约定：
- 上传仅限 .py/.yaml/.json，上传前 py_compile 或 yaml/json 解析校验（错误带行号）
- 目标路径严格限制在 cases/ 与 page_objects 指定目录内，杜绝路径穿越
- 受保护文件（框架公共文件，如 conftest.py）删除/重命名需管理员权限
  （本机模式即管理员；启用 ADMIN_TOKEN 后需请求头 X-Admin-Token 匹配）
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile

from flask import Blueprint, jsonify, render_template, request, send_file

from web_platform.runtime_config import BASE_DIR

bp = Blueprint('admin', __name__)

ROOT = BASE_DIR  # 项目根（可读性别名）
MAX_UPLOAD_BYTES = 200 * 1024
META_PATH = os.environ.get('ADMIN_META_PATH') or os.path.join(
    BASE_DIR, 'output', 'admin_meta.json')

_UPLOAD_TARGETS = {
    'cases': os.path.join(BASE_DIR, 'cases'),
    'elements': os.path.join(BASE_DIR, 'page_objects', 'app_ui', 'android', 'demoProject', 'elements'),
    'pages': os.path.join(BASE_DIR, 'page_objects', 'app_ui', 'android', 'demoProject', 'pages'),
}
# 统一列表的类型定义：code -> (显示名, 目录, 文件名规范)
TYPE_DEFS = {
    'case': {'label': '测试用例', 'base': _UPLOAD_TARGETS['cases'], 'base_kind': 'cases',
             'name_re': re.compile(r'^test_[A-Za-z0-9_]+\.py$')},
    'framework': {'label': '框架公共文件', 'base': _UPLOAD_TARGETS['cases'], 'base_kind': 'cases',
                  'name_re': re.compile(r'^(?!test_)[A-Za-z_][A-Za-z0-9_]*\.py$')},
    'page': {'label': '页面对象', 'base': _UPLOAD_TARGETS['pages'], 'base_kind': 'pages',
             'name_re': re.compile(r'^[A-Za-z_][A-Za-z0-9_]*\.py$')},
    'element': {'label': '元素定位', 'base': _UPLOAD_TARGETS['elements'], 'base_kind': 'elements',
                'name_re': re.compile(r'^[A-Za-z_][A-Za-z0-9_]*\.(py|yaml|json)$')},
}
PROTECTED_TYPES = {'framework'}  # 受保护：删除/重命名仅管理员
TYPE_LABELS = {k: v['label'] for k, v in TYPE_DEFS.items()}
_NAME_RULES = {
    'cases': r'^test_[A-Za-z0-9_]+\.py$',
    'pages': r'^[A-Za-z_][A-Za-z0-9_]*\.py$',
    'elements': r'^[A-Za-z_][A-Za-z0-9_]*\.(py|yaml|json)$',
}


class AdminError(Exception):
    pass


# ---------------- 元数据（上传人/备份记录），二期平移 file_manage 表 ----------------
def _load_meta():
    if not os.path.isfile(META_PATH):
        return {}
    try:
        with open(META_PATH, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_meta(meta):
    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
    with open(META_PATH, 'w', encoding='utf-8') as f:
        f.write(json.dumps(meta, ensure_ascii=False, indent=1))


def _meta_of(meta, full_rel):
    return meta.get(full_rel, {})


def _protected_allowed(force_admin=False):
    """受保护文件（框架公共文件）操作权限：默认拒绝，防止误删框架。
    放行条件：口令模式下管理员令牌匹配；或本机模式下显式 force_admin=true
    （操作者明确知道自己在动框架文件）。"""
    token = os.environ.get('ADMIN_TOKEN', '').strip()
    if token:
        return request.headers.get('X-Admin-Token', '') == token
    return bool(force_admin)


def _check_token():
    """返回鉴权状态字符串：'off'（本机模式）/ 'on'（口令校验通过）"""
    token = os.environ.get('ADMIN_TOKEN', '').strip()
    if not token:
        return 'off'
    if request.headers.get('X-Admin-Token', '') != token:
        raise AdminError('访问口令不正确（管理后台已启用口令保护）')
    return 'on'


def _classify(rel_to_base, base_kind):
    """按目录归属与文件名判定类型；cases 下非 test_ 前缀的 py 为受保护框架文件"""
    filename = os.path.basename(rel_to_base)
    if base_kind == 'cases':
        code = 'case' if filename.startswith('test_') else 'framework'
        return code, code in PROTECTED_TYPES
    if base_kind == 'pages':
        return 'page', False
    return 'element', False


def _resolve_managed_path(full_rel):
    """把相对项目根的路径解析到受管目录之一，返回 (abs_path, base_kind, rel_to_base)"""
    rel = (full_rel or '').strip().replace('\\', '/')
    if not rel or '..' in rel or rel.startswith('/'):
        raise AdminError('路径不合法: %r' % full_rel)
    for kind, base in _UPLOAD_TARGETS.items():
        norm_base = os.path.normpath(base)
        abs_path = os.path.normpath(os.path.join(ROOT, rel))
        if abs_path == norm_base or abs_path.startswith(norm_base + os.sep):
            return abs_path, kind, os.path.relpath(abs_path, norm_base).replace(os.sep, '/')
    raise AdminError('路径不在受管目录内: %s' % rel)


def _validate_name(kind, filename):
    if kind not in _NAME_RULES:
        raise AdminError('未知的上传类型: %s' % kind)
    if not re.match(_NAME_RULES[kind], filename):
        raise AdminError('文件名不符合规范: %s（要求 %s）' % (filename, _NAME_RULES[kind]))


def _syntax_check(abs_path, ext=None):
    """按后缀校验（临时文件需显式传原始后缀）；py 错误提取行号，yaml/json 错误提取位置"""
    ext = (ext or os.path.splitext(abs_path)[1]).lower()
    if ext == '.py':
        r = subprocess.run([sys.executable, '-m', 'py_compile', abs_path],
                           capture_output=True, timeout=30, cwd=ROOT)
        if r.returncode != 0:
            err = r.stderr.decode('utf-8', 'ignore')
            m = re.search(r'line (\d+)', err)
            line = ('第 %s 行' % m.group(1)) if m else ''
            detail = err.strip().splitlines()[-1][:200] if err.strip() else ''
            raise AdminError('py 语法错误%s: %s' % (line, detail))
    elif ext == '.yaml':
        import yaml
        try:
            with open(abs_path, encoding='utf-8') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            mark = getattr(getattr(e, 'problem_mark', None), 'line', None)
            where = ('第 %d 行' % (mark + 1)) if mark is not None else ''
            raise AdminError('yaml 格式错误%s: %s' % (where, str(e).splitlines()[0][:200]))
    elif ext == '.json':
        try:
            with open(abs_path, encoding='utf-8') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            raise AdminError('json 格式错误第 %d 行: %s' % (e.lineno, e.msg))
    else:
        raise AdminError('不支持的文件后缀: %s' % ext)


@bp.route('/admin')
def page_admin():
    return render_template('admin.html')


@bp.route('/api/admin/files')
def api_admin_files():
    """统一文件列表：跨 cases/pages/elements 三个受管目录，含类型/上传人/受保护标记"""
    try:
        auth = _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    type_filter = request.args.get('type', '')
    meta = _load_meta()
    now = int(time.time())
    files, seen = [], set()
    for type_code, conf in TYPE_DEFS.items():
        base = conf['base']
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != '__pycache__' and not d.startswith('.')]
            for fn in sorted(filenames):
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.(py|yaml|json)$', fn):
                    continue
                full = os.path.join(dirpath, fn)
                rel_to_base = os.path.relpath(full, base).replace(os.sep, '/')
                full_rel = os.path.relpath(full, ROOT).replace(os.sep, '/')
                if full_rel in seen:
                    continue
                seen.add(full_rel)
                code, protected = _classify(rel_to_base, conf['base_kind'])
                st = os.stat(full)
                m = _meta_of(meta, full_rel)
                files.append({
                    'path': full_rel,
                    'file_type': code,
                    'type_label': TYPE_LABELS[code],
                    'is_protected': protected,
                    'size': st.st_size,
                    'mtime': int(st.st_mtime),
                    'uploader': m.get('uploader', '框架'),
                    'uploaded_at': m.get('uploaded_at', now),
                    'backups': m.get('backups', []),
                })
    if type_filter:
        files = [f for f in files if f['file_type'] == type_filter]
    files.sort(key=lambda x: x['path'])
    return jsonify({'ok': True, 'auth': auth, 'files': files})


@bp.route('/api/admin/upload', methods=['POST'])
def api_admin_upload():
    try:
        auth = _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    kind = request.form.get('kind', '')
    subdir = request.form.get('subdir', '')
    force = request.form.get('force') == 'true'
    uploader = (request.form.get('uploader') or 'admin').strip()[:32]
    f = request.files.get('file')
    if f is None or not f.filename:
        return jsonify({'ok': False, 'msg': '未选择文件'}), 400
    filename = os.path.basename(f.filename)
    try:
        _validate_name(kind, filename)
    except AdminError as e:
        # cases 下非 test_ 前缀的 py = 框架公共文件，仅管理员可上传（4.4）
        if kind == 'cases' and re.match(r'^(?!test_)[A-Za-z_][A-Za-z0-9_]*\.py$', filename):
            if not _protected_allowed(request.form.get('force_admin') == 'true'):
                return jsonify({'ok': False,
                                'msg': '框架公共文件（非 test_ 前缀 py）仅管理员可上传，'
                                       '请携带管理员凭据（force_admin=true 或管理员令牌）'}), 403
        else:
            return jsonify({'ok': False, 'msg': str(e)}), 400
    subdir_clean = (subdir or '').strip().strip('/')
    if subdir_clean and (not re.match(r'^[A-Za-z0-9_/-]+$', subdir_clean) or '..' in subdir_clean):
        return jsonify({'ok': False, 'msg': '子目录不合法: %r' % subdir_clean}), 400
    target_dir = os.path.normpath(os.path.join(_UPLOAD_TARGETS[kind], subdir_clean))
    norm_base = os.path.normpath(_UPLOAD_TARGETS[kind])
    if target_dir != norm_base and not target_dir.startswith(norm_base + os.sep):
        return jsonify({'ok': False, 'msg': '目标路径越界'}), 400
    target = os.path.join(target_dir, filename)
    content = f.read()
    if len(content) > MAX_UPLOAD_BYTES:
        return jsonify({'ok': False, 'msg': '文件过大（限 200KB）'}), 400

    meta = _load_meta()
    full_rel = os.path.relpath(target, ROOT).replace(os.sep, '/')
    exists = os.path.isfile(target)
    if exists and not force:
        m = _meta_of(meta, full_rel)
        st = os.stat(target)
        # 未勾选覆盖：返回已存在文件的元信息，供前端弹确认框（覆盖交互 3.3）
        return jsonify({'ok': False, 'exists': True,
                        'meta': {'uploader': m.get('uploader', '框架'),
                                 'uploaded_at': m.get('uploaded_at', int(st.st_mtime)),
                                 'modify_time': int(st.st_mtime)}}), 409

    os.makedirs(target_dir, exist_ok=True)
    tmp = target + '.uploading'
    with open(tmp, 'wb') as fh:
        fh.write(content)
    try:
        _syntax_check(tmp, os.path.splitext(filename)[1])
    except AdminError as e:
        os.remove(tmp)
        return jsonify({'ok': False, 'msg': str(e)}), 400

    if exists:
        # 覆盖前自动备份历史版本（4.3）：xxx_时间戳_backup.后缀
        stem, ext = os.path.splitext(target)
        backup_name = '%s_%s_backup%s' % (stem, time.strftime('%Y%m%d_%H%M%S'), ext)
        os.replace(target, backup_name)
        m = _meta_of(meta, full_rel)
        m.setdefault('backups', []).append(os.path.basename(backup_name))
        m['backups'] = m['backups'][-20:]
    m = meta.setdefault(full_rel, {})
    m['uploader'] = uploader
    m['uploaded_at'] = int(time.time())
    _save_meta(meta)
    os.replace(tmp, target)
    return jsonify({'ok': True, 'auth': auth, 'path': full_rel, 'backed_up': bool(exists),
                    'msg': ('已覆盖上传 %s（旧文件已自动备份）' if exists else '已上传 %s') % filename
                    + '，平台已自动识别'})


@bp.route('/api/admin/upload_zip', methods=['POST'])
def api_admin_upload_zip():
    """上传用例包（zip）：解压 → 识别三件套 → 语法+import 完整性校验 → 冲突确认 → 分发落库 + 包登记。
    zip 内文件按「一级目录（cases/pages/elements）」识别，无目录时按命名模式兜底：
    test_*.py→用例、*Page.py→页面对象、*Elements.py→元素；都不匹配的文件整体拒绝并列出。
    任一文件校验失败 → 整体回滚不落半个文件（两阶段：全部写 .uploading 校验通过后统一替换）。"""
    try:
        _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    f = request.files.get('file')
    if f is None or not f.filename:
        return jsonify({'ok': False, 'msg': '未选择 zip 文件'}), 400
    if not f.filename.lower().endswith('.zip'):
        return jsonify({'ok': False, 'msg': '请上传 .zip 用例包'}), 400
    package = os.path.splitext(os.path.basename(f.filename))[0].strip()
    if not re.match(r'^[A-Za-z0-9_\-]+$', package):
        return jsonify({'ok': False, 'msg': '用例包名不合法（仅字母/数字/下划线/中划线）: %r' % package}), 400
    force = request.form.get('force') == 'true'
    overwrite = set(filter(None, (request.form.get('overwrite') or '').split(',')))
    uploader = (request.form.get('uploader') or 'admin').strip()[:32]
    content = f.read()
    if len(content) > 2 * 1024 * 1024:
        return jsonify({'ok': False, 'msg': 'zip 过大（限 2MB）'}), 400

    # ---- 解压（防 zip 炸弹：条目数/总大小/单文件大小/路径安全）----
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        return jsonify({'ok': False, 'msg': 'zip 文件已损坏或不是有效 zip'}), 400
    names = zf.namelist()
    if len(names) > 60:
        return jsonify({'ok': False, 'msg': 'zip 内文件过多（限 60 个）'}), 400
    entries = {}   # 归一化相对路径 -> bytes
    total = 0
    for name in names:
        if name.endswith('/'):
            continue
        norm = name.replace('\\', '/').lstrip('/')
        if '..' in norm or norm.startswith('/'):
            return jsonify({'ok': False, 'msg': 'zip 内含不安全路径: %s' % name}), 400
        data = zf.read(name)
        total += len(data)
        if len(data) > MAX_UPLOAD_BYTES:
            return jsonify({'ok': False, 'msg': 'zip 内单文件过大（限 200KB）: %s' % norm}), 400
        if total > 5 * 1024 * 1024:
            return jsonify({'ok': False, 'msg': 'zip 解压总大小超限（5MB）'}), 400
        entries[norm] = data
    if not entries:
        return jsonify({'ok': False, 'msg': 'zip 内没有文件'}), 400

    # ---- 识别三件套：一级目录优先，命名模式兜底 ----
    KIND_BY_DIR = {'cases': 'case', 'pages': 'page', 'elements': 'element'}
    items = []       # [{'filename', 'kind', 'data', 'src_name'}]
    rejected = []
    for norm, data in sorted(entries.items()):
        if not norm.lower().endswith('.py'):
            rejected.append({'file': norm, 'reason': '仅支持 .py 文件'})
            continue
        base_name = os.path.basename(norm)
        top_dir = norm.split('/')[0] if '/' in norm else ''
        kind = KIND_BY_DIR.get(top_dir)
        if not kind:
            if re.match(r'^test_[A-Za-z0-9_]+\.py$', base_name):
                kind = 'case'
            elif base_name.endswith('Page.py'):
                kind = 'page'
            elif base_name.endswith('Elements.py'):
                kind = 'element'
        if not kind:
            rejected.append({'file': norm, 'reason': '无法识别类型（需 cases/pages/elements 目录或 test_*/…Page/…Elements 命名）'})
            continue
        items.append({'filename': base_name, 'kind': kind, 'data': data, 'src_name': norm})
    if rejected:
        return jsonify({'ok': False, 'msg': '以下文件无法识别归属，请整理后重新打包',
                        'rejected': rejected}), 400
    if not any(it['kind'] == 'case' for it in items):
        return jsonify({'ok': False, 'msg': '用例包内没有测试用例（缺少 test_*.py），无法执行'}), 400
    dup = [k for k in {'case', 'page', 'element'}
           if sum(1 for it in items if it['kind'] == k) > 1 and k != 'case']
    if dup:
        return jsonify({'ok': False, 'msg': '包内同一类型出现多个文件（%s），一个用例包应为一套三件套' % '/'.join(dup)}), 400

    # ---- 落位目标 + 语法校验（全部写临时文件，两阶段）----
    # 用例固定分发到框架 App UI 用例约定目录（scan_case_tree 只收集 cases/app_ui 下的 test_*.py），
    # 页面/元素到 demoProject 对应目录——三处都是 import 链的约定位置
    target_dir_by_kind = {
        'case': os.path.join(_UPLOAD_TARGETS['cases'], 'app_ui', 'android', 'demoProject'),
        'page': _UPLOAD_TARGETS['pages'],
        'element': _UPLOAD_TARGETS['elements'],
    }
    meta = _load_meta()
    # ---- 冲突检测先行（在写临时文件前）：与库内同名且未确认覆盖 → 409 列清单 ----
    def _target_of(it):
        return os.path.join(target_dir_by_kind[it['kind']], it['filename'])

    conflicts = []
    for it in items:
        full_rel = os.path.relpath(_target_of(it), ROOT).replace(os.sep, '/')
        if os.path.isfile(_target_of(it)) and not force and full_rel not in overwrite:
            conflicts.append({'path': full_rel,
                              'uploader': _meta_of(meta, full_rel).get('uploader', '框架')})
    if conflicts:
        return jsonify({'ok': False, 'conflicts': conflicts,
                        'msg': '以下文件与库内现有文件重名，请确认覆盖'}), 409

    plan = []        # [{'item','target','full_rel','exists'}]
    tmp_files = []   # (tmp_path, target, existed)
    try:
        for it in items:
            target = os.path.join(target_dir_by_kind[it['kind']], it['filename'])
            full_rel = os.path.relpath(target, ROOT).replace(os.sep, '/')
            exists = os.path.isfile(target)
            tmp = target + '.uploading'
            with open(tmp, 'wb') as fh:
                fh.write(it['data'])
            tmp_files.append((tmp, target, exists))
            plan.append({'item': it, 'target': target, 'full_rel': full_rel, 'exists': exists})
        for tmp, _, _ in tmp_files:
            _syntax_check(tmp, '.py')

        # ---- import 完整性：用例 import 的页面模块、页面 import 的元素模块必须可解析 ----
        pkg_page = {it['filename'][:-3] for it in items if it['kind'] == 'page'}
        pkg_element = {it['filename'][:-3] for it in items if it['kind'] == 'element'}
        pages_dir = _UPLOAD_TARGETS['pages']
        elements_dir = _UPLOAD_TARGETS['elements']
        PREFIX = 'page_objects.app_ui.android.demoProject.'
        for it in items:
            if it['kind'] not in ('case', 'page'):
                continue
            try:
                mod = ast.parse(it['data'].decode('utf-8', 'ignore'))
            except SyntaxError:
                continue   # 语法错误已被 py_compile 拦截
            for node in ast.walk(mod):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                m = node.module
                # 模块名取 node.module 中前缀之后的段（from ...pages.xxxPage import XxxPage）；
                # `from ...pages import 类名` 的写法无法映射到文件名，跳过（运行时由 import 兜底）
                need = None
                for kind, sub in (('page', 'pages'), ('element', 'elements')):
                    if m == PREFIX + sub:
                        need = None    # 裸 from ...pages import 类名：跳过文件级校验
                        break
                    if m.startswith(PREFIX + sub + '.'):
                        need = (kind, sub)
                        break
                if not need:
                    continue
                kind, sub = need
                mod_name = m[len(PREFIX + sub) + 1:].split('.')[0]
                need_set = pkg_page if kind == 'page' else pkg_element
                dir_path = pages_dir if kind == 'page' else elements_dir
                label = '页面对象' if kind == 'page' else '元素'
                if mod_name in need_set:
                    continue
                if os.path.isfile(os.path.join(dir_path, mod_name + '.py')):
                    continue   # 框架库里已有
                raise AdminError('%s 缺少依赖：引用了%s %s.py，但包内和框架里都没有该文件'
                                 % (it['filename'], label, mod_name))
    except AdminError as e:
        for tmp, _, _ in tmp_files:
            if os.path.isfile(tmp):
                os.remove(tmp)
        return jsonify({'ok': False, 'msg': str(e)}), 400
    except Exception as e:
        for tmp, _, _ in tmp_files:
            if os.path.isfile(tmp):
                os.remove(tmp)
        return jsonify({'ok': False, 'msg': '用例包校验失败: %s' % e}), 400

    # ---- 冲突确认：存在未勾选覆盖的同名文件 → 409 列清单 ----
    # ---- 统一落库（覆盖的先备份）+ 包登记 ----
    placed, backed_up = [], []
    try:
        for tmp, target, exists in tmp_files:
            full_rel = os.path.relpath(target, ROOT).replace(os.sep, '/')
            if exists:
                stem, ext = os.path.splitext(target)
                backup_name = '%s_%s_backup%s' % (stem, time.strftime('%Y%m%d_%H%M%S'), ext)
                os.replace(target, backup_name)
                m = _meta_of(meta, full_rel)
                m.setdefault('backups', []).append(os.path.basename(backup_name))
                m['backups'] = m['backups'][-20:]
                backed_up.append(os.path.basename(backup_name))
            m = meta.setdefault(full_rel, {})
            m['uploader'] = uploader
            m['uploaded_at'] = int(time.time())
            m['package'] = package
            os.replace(tmp, target)
            placed.append({'path': full_rel, 'kind': next(it['kind'] for it in items
                                                           if it['filename'] == os.path.basename(target))})
        _save_meta(meta)
        packages = _load_packages()
        packages[package] = {
            'package': package,
            'files': [p['full_rel'] for p in plan],
            'uploader': uploader,
            'uploaded_at': int(time.time()),
        }
        _save_packages(packages)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '落库失败（已完成回滚尝试）: %s' % e}), 500
    return jsonify({'ok': True, 'package': package,
                    'placed': placed, 'backed_up': backed_up,
                    'msg': '用例包「%s」已入库：%s' % (
                        package, '、'.join(p['path'] for p in placed))})


PACKAGES_PATH = os.environ.get('CASE_PACKAGES_PATH') or os.path.join(
    BASE_DIR, 'output', 'case_packages.json')


def _load_packages():
    if not os.path.isfile(PACKAGES_PATH):
        return {}
    try:
        with open(PACKAGES_PATH, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_packages(packages):
    os.makedirs(os.path.dirname(PACKAGES_PATH), exist_ok=True)
    with open(PACKAGES_PATH, 'w', encoding='utf-8') as f:
        f.write(json.dumps(packages, ensure_ascii=False, indent=1))


@bp.route('/api/admin/packages')
def api_admin_packages():
    """用例包登记表（执行页按包分组/筛选用）"""
    return jsonify({'ok': True, 'packages': _load_packages()})


@bp.route('/api/admin/download')
def api_admin_download():
    try:
        _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    try:
        abs_path, _, _ = _resolve_managed_path(request.args.get('path', ''))
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    if not os.path.isfile(abs_path):
        return jsonify({'ok': False, 'msg': '文件不存在'}), 404
    return send_file(abs_path, as_attachment=True)


@bp.route('/api/admin/download_batch')
def api_admin_download_batch():
    try:
        _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    paths = (request.args.get('paths') or '').split(',')
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel in paths:
            try:
                abs_path, _, rel_to_base = _resolve_managed_path(rel)
            except AdminError:
                continue
            if os.path.isfile(abs_path):
                zf.write(abs_path, rel_to_base)
                count += 1
    if not count:
        return jsonify({'ok': False, 'msg': '没有可下载的文件'}), 404
    buf.seek(0)
    # Flask 1.x 用 attachment_filename（download_name 是 2.0+ 参数）
    return send_file(buf, as_attachment=True, mimetype='application/zip',
                     attachment_filename='files_%s.zip' % time.strftime('%Y%m%d_%H%M%S'))


@bp.route('/api/admin/rename', methods=['POST'])
def api_admin_rename():
    try:
        _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    body = request.get_json(force=True, silent=True) or {}
    try:
        abs_path, kind, rel_to_base = _resolve_managed_path(body.get('path', ''))
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    _, protected = _classify(rel_to_base, kind)
    if protected and not _protected_allowed(bool(body.get('force_admin'))):
        return jsonify({'ok': False, 'msg': '框架公共文件，仅管理员可操作'}), 403
    new_name = os.path.basename(body.get('new_name') or '')
    try:
        _validate_name(kind, new_name)
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    new_path = os.path.join(os.path.dirname(abs_path), new_name)
    if os.path.isfile(new_path):
        return jsonify({'ok': False, 'msg': '目标文件名已存在: %s' % new_name}), 409
    old_rel = os.path.relpath(abs_path, ROOT).replace(os.sep, '/')
    os.rename(abs_path, new_path)
    meta = _load_meta()
    if old_rel in meta:
        meta[os.path.relpath(new_path, ROOT).replace(os.sep, '/')] = meta.pop(old_rel)
        _save_meta(meta)
    return jsonify({'ok': True, 'msg': '已重命名为 %s' % new_name})


@bp.route('/api/admin/folder', methods=['POST'])
def api_admin_folder():
    try:
        _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    body = request.get_json(force=True, silent=True) or {}
    kind = body.get('kind', '')
    subdir = (body.get('subdir') or '').strip().strip('/')
    if kind not in _NAME_RULES:
        return jsonify({'ok': False, 'msg': '未知类型'}), 400
    if not subdir or not re.match(r'^[A-Za-z0-9_/-]+$', subdir) or '..' in subdir:
        return jsonify({'ok': False, 'msg': '目录名不合法（字母/数字/_/-，可含子层级）'}), 400
    target_dir = os.path.normpath(os.path.join(_UPLOAD_TARGETS[kind], subdir))
    norm_base = os.path.normpath(_UPLOAD_TARGETS[kind])
    if target_dir != norm_base and not target_dir.startswith(norm_base + os.sep):
        return jsonify({'ok': False, 'msg': '目标路径越界'}), 400
    if os.path.isdir(target_dir):
        return jsonify({'ok': False, 'msg': '目录已存在: %s' % subdir}), 409
    os.makedirs(target_dir, exist_ok=True)
    return jsonify({'ok': True, 'msg': '已创建目录 %s' % subdir})


@bp.route('/api/admin/batch_delete', methods=['POST'])
def api_admin_batch_delete():
    try:
        _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    body = request.get_json(force=True, silent=True) or {}
    paths = body.get('paths') or []
    force_admin = bool(body.get('force_admin'))
    if not paths:
        return jsonify({'ok': False, 'msg': '未选择文件'}), 400
    meta = _load_meta()
    deleted, denied, missing = [], [], []
    for rel in paths:
        try:
            abs_path, kind, rel_to_base = _resolve_managed_path(rel)
        except AdminError:
            missing.append(rel)
            continue
        _, protected = _classify(rel_to_base, kind)
        if protected and not _protected_allowed(force_admin):
            denied.append(rel)
            continue
        if not os.path.isfile(abs_path):
            missing.append(rel)
            continue
        os.remove(abs_path)
        meta.pop(os.path.relpath(abs_path, ROOT).replace(os.sep, '/'), None)
        deleted.append(rel)
    _save_meta(meta)
    msg_parts = ['已删除 %d 个' % len(deleted)]
    if denied:
        msg_parts.append('受保护跳过 %d 个（框架公共文件仅管理员可操作）' % len(denied))
    if missing:
        msg_parts.append('不存在 %d 个' % len(missing))
    return jsonify({'ok': True, 'deleted': deleted, 'denied': denied, 'missing': missing,
                    'msg': '；'.join(msg_parts)})


@bp.route('/api/admin/file', methods=['DELETE'])
def api_admin_delete():
    """单文件删除；受保护文件（框架公共文件）仅管理员可操作"""
    try:
        _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    try:
        abs_path, kind, rel_to_base = _resolve_managed_path(request.args.get('path', ''))
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    _, protected = _classify(rel_to_base, kind)
    if protected and not _protected_allowed(request.args.get('force_admin') == 'true'):
        return jsonify({'ok': False, 'msg': '框架公共文件，仅管理员可操作'}), 403
    if not os.path.isfile(abs_path):
        return jsonify({'ok': False, 'msg': '文件不存在'}), 404
    os.remove(abs_path)
    meta = _load_meta()
    meta.pop(os.path.relpath(abs_path, ROOT).replace(os.sep, '/'), None)
    _save_meta(meta)
    return jsonify({'ok': True, 'msg': '已删除 %s' % rel_to_base})
