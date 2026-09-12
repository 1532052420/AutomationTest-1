# -*- coding: utf-8 -*-
"""Web 执行平台 · 管理后台（用例 / 元素 / 页面对象 上传与管理）

面向团队协作：组员通过网页上传用例与元素文件，平台自动识别（用例树、
方法目录均实时扫描磁盘，上传即生效），无需每人配置本地环境。

安全约定：
- 仅接受 .py 文件，上传前必须通过 py_compile 语法校验
- 目标路径严格限制在 cases/ 与 page_objects 指定目录内，杜绝路径穿越
- 访问口令：设置环境变量 ADMIN_TOKEN 后，所有管理接口要求请求头
  X-Admin-Token 匹配；未设置时为"本机模式"不鉴权（仅建议本机使用）
- 同名文件覆盖需显式 force=true
"""
import os
import re
import subprocess
import sys

from flask import Blueprint, jsonify, render_template, request

from web_platform.runtime_config import BASE_DIR

bp = Blueprint('admin', __name__)

MAX_UPLOAD_BYTES = 200 * 1024
UPLOAD_TARGETS = {
    'cases': {'dir': os.path.join(BASE_DIR, 'cases'), 'name_re': r'^test_[A-Za-z0-9_]+\.py$',
              'label': '测试用例（test_*.py）'},
    'elements': {'dir': os.path.join(BASE_DIR, 'page_objects', 'app_ui', 'android', 'demoProject', 'elements'),
                 'name_re': r'^[A-Za-z_][A-Za-z0-9_]*\.py$', 'label': '元素仓库（xxxElements.py）'},
    'pages': {'dir': os.path.join(BASE_DIR, 'page_objects', 'app_ui', 'android', 'demoProject', 'pages'),
              'name_re': r'^[A-Za-z_][A-Za-z0-9_]*\.py$', 'label': '页面对象（xxxPage.py）'},
}


class AdminError(Exception):
    pass


def _check_token():
    """返回鉴权状态字符串：'off'（本机模式）/ 'on'（口令校验通过）"""
    token = os.environ.get('ADMIN_TOKEN', '').strip()
    if not token:
        return 'off'  # 本机模式：未配置口令
    given = request.headers.get('X-Admin-Token', '')
    if given != token:
        raise AdminError('访问口令不正确（管理后台已启用口令保护）')
    return 'on'


def _resolve_target(kind, subdir, filename):
    if kind not in UPLOAD_TARGETS:
        raise AdminError('未知的上传类型: %s' % kind)
    conf = UPLOAD_TARGETS[kind]
    if not re.match(conf['name_re'], filename):
        raise AdminError('文件名不符合规范（%s）: %s' % (conf['label'], filename))
    subdir = (subdir or '').strip().strip('/')
    if subdir:
        if not re.match(r'^[A-Za-z0-9_/-]+$', subdir) or '..' in subdir:
            raise AdminError('子目录不合法: %r' % subdir)
    target_dir = os.path.normpath(os.path.join(conf['dir'], subdir))
    norm_base = os.path.normpath(conf['dir'])
    if target_dir != norm_base and not target_dir.startswith(norm_base + os.sep):
        raise AdminError('目标路径越界')
    return conf, os.path.join(target_dir, filename), target_dir


def _compile_check(path):
    r = subprocess.run([sys.executable, '-m', 'py_compile', path],
                       capture_output=True, timeout=30, cwd=BASE_DIR)
    if r.returncode != 0:
        raise AdminError('语法校验未通过: %s' % r.stderr.decode('utf-8', 'ignore')[-300:])


@bp.route('/admin')
def page_admin():
    return render_template('admin.html')


@bp.route('/api/admin/files')
def api_admin_files():
    try:
        auth = _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    kind = request.args.get('kind', 'cases')
    if kind not in UPLOAD_TARGETS:
        return jsonify({'ok': False, 'msg': '未知类型'}), 400
    base = UPLOAD_TARGETS[kind]['dir']
    files = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != '__pycache__' and not d.startswith('.')]
        for fn in sorted(filenames):
            if not fn.endswith('.py'):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, base).replace(os.sep, '/')
            st = os.stat(full)
            files.append({'path': rel, 'size': st.st_size,
                          'mtime': int(st.st_mtime)})
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
    f = request.files.get('file')
    if f is None or not f.filename:
        return jsonify({'ok': False, 'msg': '未选择文件'}), 400
    filename = os.path.basename(f.filename)
    try:
        conf, target, target_dir = _resolve_target(kind, subdir, filename)
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    content = f.read()
    if len(content) > MAX_UPLOAD_BYTES:
        return jsonify({'ok': False, 'msg': '文件过大（限 200KB）'}), 400
    if os.path.isfile(target) and not force:
        return jsonify({'ok': False, 'msg': '文件已存在：%s（确认覆盖请勾选"覆盖同名文件"）' %
                        os.path.relpath(target, BASE_DIR), 'exists': True}), 409
    os.makedirs(target_dir, exist_ok=True)
    tmp = target + '.uploading'
    with open(tmp, 'wb') as fh:
        fh.write(content)
    try:
        _compile_check(tmp)
    except AdminError as e:
        os.remove(tmp)
        return jsonify({'ok': False, 'msg': str(e)}), 400
    os.replace(tmp, target)
    return jsonify({'ok': True, 'auth': auth,
                    'path': os.path.relpath(target, BASE_DIR).replace(os.sep, '/'),
                    'msg': '已上传 %s，平台已自动识别' % filename})


@bp.route('/api/admin/file', methods=['DELETE'])
def api_admin_delete():
    try:
        auth = _check_token()
    except AdminError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 401
    kind = request.args.get('kind', '')
    rel = request.args.get('path', '')
    if kind not in UPLOAD_TARGETS:
        return jsonify({'ok': False, 'msg': '未知类型'}), 400
    base = os.path.normpath(UPLOAD_TARGETS[kind]['dir'])
    target = os.path.normpath(os.path.join(base, rel))
    if not target.startswith(base + os.sep) or not target.endswith('.py'):
        return jsonify({'ok': False, 'msg': '路径不合法'}), 400
    if not os.path.isfile(target):
        return jsonify({'ok': False, 'msg': '文件不存在'}), 404
    os.remove(target)
    pyc = os.path.join(os.path.dirname(target), '__pycache__')
    return jsonify({'ok': True, 'msg': '已删除 %s' % rel.replace(os.sep, '/')})
