# -*- coding: utf-8 -*-
"""代码调试 · 交互式调试工具（真实可输入：用户填参数 → 执行 → 返回数据）

与 dbg_checks_* 的"固定检查项"不同，本模块的每个工具接受用户输入参数：
- http_request   真实发起 HTTP 请求（走框架 DoRequest），返回状态码/响应头/响应体
- text_assert    文本 + 正则匹配调试，返回匹配结果与各断言工具判定
- element_build  构造 ElementInfo（定位方式/定位值/等待），返回元素数据 JSON
- po_generate    生成「页面对象 + 元素仓库」框架代码（风格对齐 kuaigeLoginPage 体系）
- po_save        把生成的代码写入 page_objects 对应目录（存在时需确认覆盖）

所有工具只读或写入 page_objects 指定目录，不触碰其他框架文件。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PAGES_DIR = os.path.join(ROOT, 'page_objects', 'app_ui', 'android', 'demoProject', 'pages')
ELEMENTS_DIR = os.path.join(ROOT, 'page_objects', 'app_ui', 'android', 'demoProject', 'elements')


class ToolError(Exception):
    """用户输入不合法（返回给页面展示，不算系统异常）"""


# ---------------------------------------------------------------- 工具 1：HTTP 请求
def tool_http_request(params):
    from urllib.parse import urlparse
    from common.httpclient.doRequest import DoRequest
    url = str(params.get('url') or '').strip()
    if not re.match(r'^https?://', url):
        raise ToolError('URL 必须以 http:// 或 https:// 开头')
    method = str(params.get('method') or 'get').lower()
    if method not in ('get', 'post_form', 'put'):
        raise ToolError('method 仅支持 get / post_form / put')
    parsed = urlparse(url)
    base = '%s://%s' % (parsed.scheme, parsed.netloc)
    path = parsed.path or '/'
    if parsed.query:
        path += '?' + parsed.query
    params_dict = params.get('params') or {}
    headers = params.get('headers') or {}
    timeout = min(max(int(params.get('timeout') or 20), 1), 45)
    client = DoRequest(base, timeout=timeout)
    try:
        if headers:
            client.setHeaders({str(k): str(v) for k, v in headers.items()})
        if method == 'get':
            r = client.get(path, params_dict or None)
        elif method == 'post_form':
            r = client.post_with_form(path, params_dict or None)
        else:
            r = client.put(path, params_dict or None)
        body = (r.body or '')
        return {
            'status_code': r.status_code,
            'cookies': r.cookies,
            'body': body[:4000] + ('…(截断，共 %d 字符)' % len(body) if len(body) > 4000 else ''),
            'body_length': len(body),
            'request': {'base': base, 'path': path, 'method': method, 'params': params_dict, 'headers': headers},
        }
    finally:
        client.closeSession()


# ---------------------------------------------------------------- 工具 2：文本断言
def tool_text_assert(params):
    import re as _re
    from common.assertTool import AssertTool
    from common.hamcrest.hamcrest import assert_that
    source = str(params.get('source') or '')
    pattern = str(params.get('pattern') or '').strip()
    if not pattern:
        raise ToolError('正则表达式不能为空')
    try:
        compiled = _re.compile(pattern)
    except _re.error as e:
        raise ToolError('正则不合法: %s' % e)
    matches = [m.group(0) for m in compiled.finditer(source)]
    first = compiled.search(source)
    # 框架两套断言工具的判定结果
    try:
        assert_tool_ok = bool(AssertTool.isRegularMatch(source, pattern))
    except Exception as e:
        assert_tool_ok = '工具异常: %s' % e
    try:
        assert_that(source).is_match_by_regexp(pattern)
        hamcrest_ok = True
    except AssertionError:
        hamcrest_ok = False
    return {
        'matched': first is not None,
        'match_text': first.group(0) if first else None,
        'groups': list(first.groups()) if first else [],
        'all_matches': matches[:50],
        'match_count': len(matches),
        'assertTool_isRegularMatch': assert_tool_ok,
        'hamcrest_is_match_by_regexp': hamcrest_ok,
    }


# ---------------------------------------------------------------- 工具 3：元素构造
def tool_element_build(params):
    from page_objects.createElement import CreateElement
    from page_objects.app_ui.locator_type import Locator_Type
    from page_objects.app_ui.wait_type import Wait_Type
    locator_type = str(params.get('locator_type') or '').strip()
    if not hasattr(Locator_Type, locator_type):
        valid = [a for a in dir(Locator_Type) if not a.startswith('_')]
        raise ToolError('locator_type 不合法，可选: %s' % ', '.join(valid))
    locator_value = str(params.get('locator_value') or '').strip()
    if not locator_value:
        raise ToolError('locator_value 不能为空')
    wait_type = str(params.get('wait_type') or '').strip()
    kwargs = {}
    if wait_type:
        if wait_type not in [a for a in dir(Wait_Type) if not a.startswith('_')]:
            valid = [a for a in dir(Wait_Type) if not a.startswith('_')]
            raise ToolError('wait_type 不合法，可选: %s' % ', '.join(valid))
        kwargs['wait_type'] = getattr(Wait_Type, wait_type)
        if params.get('wait_seconds'):
            kwargs['wait_seconds'] = int(params['wait_seconds'])
    if params.get('expected_value'):
        kwargs['expected_value'] = str(params['expected_value'])
    info = CreateElement.create(getattr(Locator_Type, locator_type), locator_value, **kwargs)
    code_line = "CreateElement.create(Locator_Type.%s, '%s'" % (locator_type, locator_value)
    if wait_type:
        code_line += ", wait_type=Wait_By.%s" % wait_type
    code_line += ")"
    return {
        'locator_type': info.locator_type,
        'locator_value': info.locator_value,
        'expected_value': info.expected_value,
        'wait_type': info.wait_type,
        'wait_expected_value': info.wait_expected_value,
        'wait_seconds': info.wait_seconds,
        'code': code_line,
    }


# ---------------------------------------------------------------- 工具 4/5：新增 PO
_PAGE_CLASS_RE = re.compile(r'^[A-Z][A-Za-z0-9_]*$')
_ELEM_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')
_ACTIONS = ('click', 'input', 'check', 'read')


def _po_validate(params):
    from page_objects.app_ui.locator_type import Locator_Type
    from page_objects.app_ui.wait_type import Wait_Type
    page_class = str(params.get('page_class') or '').strip()
    if not _PAGE_CLASS_RE.match(page_class):
        raise ToolError('页面类名必须是大驼峰（如 KuaigeLoginPage）')
    elements = params.get('elements') or []
    if not elements:
        raise ToolError('至少定义一个元素')
    lt_values = [a for a in dir(Locator_Type) if not a.startswith('_')]
    wt_values = [a for a in dir(Wait_Type) if not a.startswith('_')]
    seen = set()
    cleaned = []
    for idx, e in enumerate(elements, 1):
        name = str(e.get('name') or '').strip()
        if not _ELEM_NAME_RE.match(name):
            raise ToolError('第 %d 个元素名 %r 不合法（小驼峰/下划线，如 btn_login）' % (idx, name))
        if name in seen:
            raise ToolError('元素名重复: %s' % name)
        seen.add(name)
        lt = str(e.get('locator_type') or '').strip()
        if lt not in lt_values:
            raise ToolError('元素 %s 的定位方式不合法，可选: %s' % (name, ', '.join(lt_values)))
        value = str(e.get('locator_value') or '').strip()
        if not value:
            raise ToolError('元素 %s 的定位值不能为空' % name)
        action = str(e.get('action') or 'click').strip()
        if action not in _ACTIONS:
            raise ToolError('元素 %s 的操作类型不合法，可选: %s' % (name, '/'.join(_ACTIONS)))
        wt = str(e.get('wait_type') or '').strip()
        if wt and wt not in wt_values:
            raise ToolError('元素 %s 的等待类型不合法，可选: %s' % (name, ', '.join(wt_values)))
        cleaned.append({'name': name, 'desc': str(e.get('desc') or '').strip(), 'action': action,
                        'locator_type': lt, 'locator_value': value, 'wait_type': wt})
    return page_class, cleaned


def _po_render(params, page_class, elements):
    """生成 (elements_code, page_code, elements_file, page_file, elements_class)"""
    def snake_to_lower_camel(cls):
        return cls[0].lower() + cls[1:]

    base = page_class[:-4] if page_class.endswith('Page') else page_class
    elements_class = base + 'Elements'
    elements_file = snake_to_lower_camel(elements_class) + '.py'
    page_file = snake_to_lower_camel(page_class) + '.py'
    desc = str(params.get('page_desc') or '').strip() or page_class

    el_lines = [
        '# -*- coding: utf-8 -*-',
        '# 工具生成 · %s 元素仓库（代码审查-新增PO 生成）' % desc,
        'from page_objects.createElement import CreateElement',
        'from page_objects.app_ui.locator_type import Locator_Type',
        'from page_objects.app_ui.wait_type import Wait_Type as Wait_By',
        '',
        '',
        'class %s:' % elements_class,
        '    """%s 相关元素"""' % desc,
        '',
        '    def __init__(self):',
    ]
    for e in elements:
        wait = ''
        if e['wait_type']:
            wait = ", wait_type=Wait_By.%s" % e['wait_type']
        if e['desc']:
            el_lines.append('        # %s' % e['desc'])
        el_lines.append("        self.%s = CreateElement.create(Locator_Type.%s, '%s'%s)" % (
            e['name'], e['locator_type'], e['locator_value'], wait))
    elements_code = '\n'.join(el_lines) + '\n'

    method_tpl = {
        'click': '    def click_{n}(self):\n        """点击 {d}"""\n        self.appOperator.click(self._elements.{n})\n',
        'input': '    def input_{n}(self, text):\n        """在 {d} 输入内容"""\n        self.appOperator.sendText(self._elements.{n}, text)\n',
        'check': '    def check_{n}(self):\n        """{d} 是否可见"""\n        return self.appOperator.is_displayed(self._elements.{n})\n',
        'read': '    def read_{n}(self):\n        """读取 {d} 文本"""\n        return self.appOperator.getText(self._elements.{n})\n',
    }
    pg_lines = [
        '# -*- coding: utf-8 -*-',
        '# 工具生成 · %s（代码审查-新增PO 生成）' % desc,
        'from page_objects.app_ui.android.demoProject.elements.%s import %s' % (
            snake_to_lower_camel(elements_class), elements_class),
        '',
        '',
        'class %s:' % page_class,
        '    """%s"""' % desc,
        '',
        '    def __init__(self, appOperator):',
        '        self.appOperator = appOperator',
        '        self._elements = %s()' % elements_class,
        '',
    ]
    for e in elements:
        pg_lines.append(method_tpl[e['action']].format(n=e['name'], d=e['desc'] or e['name']))
    page_code = '\n'.join(pg_lines).rstrip() + '\n'
    return elements_code, page_code, elements_file, page_file, elements_class


def tool_po_generate(params):
    page_class, elements = _po_validate(params)
    elements_code, page_code, elements_file, page_file, elements_class = _po_render(params, page_class, elements)
    return {
        'elements_file': elements_file, 'page_file': page_file,
        'elements_class': elements_class, 'page_class': page_class,
        'elements_code': elements_code, 'page_code': page_code,
        'elements_path': 'page_objects/app_ui/android/demoProject/elements/%s' % elements_file,
        'page_path': 'page_objects/app_ui/android/demoProject/pages/%s' % page_file,
        'elements_exists': os.path.isfile(os.path.join(ELEMENTS_DIR, elements_file)),
        'page_exists': os.path.isfile(os.path.join(PAGES_DIR, page_file)),
    }


def tool_po_save(params):
    page_class, elements = _po_validate(params)
    force = bool(params.get('force'))
    generated = tool_po_generate(params)
    targets = [
        (generated['elements_code'], os.path.join(ELEMENTS_DIR, generated['elements_file']), generated['elements_exists']),
        (generated['page_code'], os.path.join(PAGES_DIR, generated['page_file']), generated['page_exists']),
    ]
    written = []
    for code, path, exists in targets:
        if exists and not force:
            raise ToolError('%s 已存在；确认覆盖请勾选「覆盖已存在文件」后重试' % os.path.relpath(path, ROOT))
        if not os.path.isfile(path):
            with open(path, 'w', encoding='utf-8') as f:
                f.write(code)
            written.append(os.path.relpath(path, ROOT))
    if not written:
        return {'written': [], 'msg': '文件均已存在且内容未变化（已勾选覆盖，跳过重写）',
                'elements_path': generated['elements_path'], 'page_path': generated['page_path']}
    return {'written': written, 'elements_path': generated['elements_path'],
            'page_path': generated['page_path'],
            'msg': '已生成 %d 个文件；用例中直接 import %s 即可使用' % (
                len(written), generated['page_class'])}


TOOLS = {
    'http_request': tool_http_request,
    'text_assert': tool_text_assert,
    'element_build': tool_element_build,
    'po_generate': tool_po_generate,
    'po_save': tool_po_save,
}
