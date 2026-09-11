# -*- coding: utf-8 -*-
"""
GUI 元素定位器 · 用例 / 页面对象生成
统一步骤结构（step dict）→ 生成：
    cases/app_ui/android/demoProject/test_xxx.py                    （用例文件）
    page_objects/app_ui/android/demoProject/pages/xxxPage.py        （页面对象文件，可选）
风格严格对齐框架现有文件（test_kuaige_login.py / kuaigeLoginPage.py）：
元素与用例分离 —— 页面方法/用例只引用元素名 self._elements.<name>，不埋定位值。
支持：新建文件 / 追加 test 方法 / 覆盖同名方法 / 自动补 import

step dict 结构（前端两个入口生成完全一致的格式）：
    {
        'type': 'click'|'input'|'long_press'|'assert_visible'|'assert_text'
                |'assert_toast'|'screenshot'|'tap'|'sleep'|'custom',
        'element': '<元素名>',   # 引用元素库；tap/sleep/custom 不填
        'param':   '',          # 输入内容/期望文本/toast文本/坐标(x,y)/秒数/自定义代码
        'desc':    '点击登录按钮',  # 可读描述（自动生成，可改）
    }
"""
import os
import re

import element_library

CASES_DIR = 'cases/app_ui/android/demoProject'
PAGES_DIR = 'page_objects/app_ui/android/demoProject/pages'

IND = '    '  # 类内方法缩进（4 空格，与框架一致）

# 步骤类型清单（前端下拉与此一致）
STEP_TYPES = [
    'click', 'input', 'long_press', 'assert_visible', 'assert_text',
    'assert_toast', 'screenshot', 'tap', 'sleep', 'custom',
]

# 元素操作类步骤需要元素；工具/兜底步骤不需要
ELEMENT_STEP_TYPES = {'click', 'input', 'long_press', 'assert_visible', 'assert_text'}

# 页面里固定实现的工具方法：已存在则不重复生成
TOOL_METHODS = {'wait_and_shot', 'tap_xy', 'assert_toast'}


def list_case_files():
    """枚举现有用例文件（test_*.py）"""
    if not os.path.isdir(CASES_DIR):
        return []
    return sorted(f for f in os.listdir(CASES_DIR) if f.startswith('test_') and f.endswith('.py'))


def list_page_files():
    """枚举现有页面对象文件"""
    if not os.path.isdir(PAGES_DIR):
        return []
    return sorted(f for f in os.listdir(PAGES_DIR) if f.endswith('.py') and f != '__init__.py')


def _read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _escape(s):
    return str(s).replace('\\', '\\\\').replace("'", "\\'")


def _q(s):
    """生成单引号字符串字面量"""
    return "'%s'" % _escape(s)


def step_desc(step):
    """步骤的可读描述（后端兜底；前端通常会自己生成并让用户可改）"""
    if step.get('desc'):
        return step['desc'].strip()
    t = step.get('type', '')
    el = step.get('element') or ''
    p = step.get('param') or ''
    return {
        'click': '点击%s' % el,
        'input': '在%s输入「%s」' % (el, p),
        'long_press': '长按%s' % el,
        'assert_visible': '断言%s出现' % el,
        'assert_text': '断言%s文本为「%s」' % (el, p),
        'assert_toast': '断言toast「%s」' % p,
        'screenshot': '截图：%s' % p,
        'tap': '点击坐标(%s)' % p,
        'sleep': '等待%s秒' % p,
        'custom': (p or '自定义代码').splitlines()[0],
    }.get(t, '未定义步骤')


def method_name(step):
    """步骤 → 页面方法名；sleep/custom 返回 None（无对应页面方法）"""
    t = step.get('type', '')
    el = step.get('element') or ''
    if t == 'click':
        return 'click_%s' % el
    if t == 'input':
        return 'input_%s' % el
    if t == 'long_press':
        return 'long_press_%s' % el
    if t == 'assert_visible':
        return 'assert_%s' % el
    if t == 'assert_text':
        return 'assert_%s_text' % el
    if t == 'assert_toast':
        return 'assert_toast'
    if t == 'screenshot':
        return 'wait_and_shot'
    if t == 'tap':
        return 'tap_xy'
    return None


def _method_block(name, doc, args, body):
    """生成一个页面方法代码块（类内 4 空格缩进，方法体内 8 空格，多行 body 逐行缩进）"""
    args_str = ', '.join(['self'] + (args or []))
    body_ind = '\n'.join((IND * 2 + line) if line.strip() else line for line in body.split('\n'))
    return '%sdef %s(%s):\n%s"""%s"""\n%s\n' % (
        IND, name, args_str, IND * 2, doc, body_ind)


def page_method_code(step):
    """步骤 → 页面方法代码块；sleep/custom 返回 None（不需要页面方法）"""
    t = step.get('type', '')
    el = step.get('element') or ''
    desc = step_desc(step)
    if t == 'click':
        return _method_block('click_%s' % el, desc, [],
                             'self.appOperator.click(self._elements.%s)' % el)
    if t == 'input':
        return _method_block('input_%s' % el, desc, ['text'],
                             'self.appOperator.sendText(self._elements.%s, text)' % el)
    if t == 'long_press':
        return _method_block('long_press_%s' % el, desc, [],
                             'self.appOperator.touch_long_press(self._elements.%s, duration_sconds=2)' % el)
    if t == 'assert_visible':
        return _method_block('assert_%s' % el, desc, [],
                             'self.appOperator.getElement(self._elements.%s)' % el)
    if t == 'assert_text':
        return _method_block('assert_%s_text' % el, desc, ['expected'],
                             "assert self.appOperator.getText(self._elements.%s) == expected, '%s'" % (el, desc))
    if t == 'assert_toast':
        return _method_block('assert_toast', desc, ['text'],
                             "assert self.appOperator.is_toast_visible(text, wait_seconds=5), '%s'" % desc)
    if t == 'screenshot':
        return _method_block('wait_and_shot', desc, ['tag'],
                             "import time\ntime.sleep(1)\nself.appOperator.get_screenshot(tag)")
    if t == 'tap':
        return _method_block('tap_xy', desc, ['x', 'y'],
                             'self.appOperator.tap(x, y)')
    return None


def case_step_line(step):
    """步骤 → 用例里的一行调用；sleep/custom 返回特殊行（非 page.xxx 调用）"""
    t = step.get('type', '')
    el = step.get('element') or ''
    p = step.get('param') or ''
    if t == 'click':
        return 'page.click_%s()' % el
    if t == 'input':
        return 'page.input_%s(%s)' % (el, _q(p))
    if t == 'long_press':
        return 'page.long_press_%s()' % el
    if t == 'assert_visible':
        return 'page.assert_%s()' % el
    if t == 'assert_text':
        return 'page.assert_%s_text(%s)' % (el, _q(p))
    if t == 'assert_toast':
        return 'page.assert_toast(%s)' % _q(p)
    if t == 'screenshot':
        return 'page.wait_and_shot(%s)' % _q(p)
    if t == 'tap':
        parts = [x.strip() for x in p.split(',') if x.strip()]
        if len(parts) >= 2:
            return 'page.tap_xy(%s, %s)' % (parts[0], parts[1])
        return 'page.tap_xy(%s)' % (parts[0] if parts else '0')
    if t == 'sleep':
        try:
            return 'time.sleep(%s)' % float(p)
        except ValueError:
            return 'time.sleep(%s)' % (p or '1')
    if t == 'custom':
        return p
    return None


# ---------------------------------------------------------------------------
# 页面对象文件生成
# ---------------------------------------------------------------------------
def _ensure_elements_import(content, elements_file, elements_class):
    """页面文件缺失元素类 import 时自动补全（class 行之前）"""
    need = 'from page_objects.app_ui.android.demoProject.elements.%s import %s' % (
        os.path.splitext(elements_file)[0], elements_class)
    if need in content:
        return content
    m = re.search(r'^(class\s+\w+[^\n]*\n)', content, re.MULTILINE)
    if not m:
        return content
    return content[:m.start()] + need + '\n\n' + content[m.start():]


def _upsert_class_method(content, cls, method_blocks, before=None):
    """把 method_blocks 追加到 class cls 的类体；同名方法先移除。
    before 指定方法名时（如 'teardown_class'），新方法插到它前面，保证 teardown 始终在类尾。
    类不存在或没有方法块时原样返回。"""
    if not method_blocks:
        return content
    m = re.search(r'^class %s\b' % re.escape(cls), content, re.MULTILINE)
    if not m:
        return content
    cls_start = m.start()
    tail = content[cls_start + 1:]
    nxt = re.search(r'^class\s', tail, re.MULTILINE)
    cls_end = cls_start + 1 + nxt.start() if nxt else len(content)
    cls_body = content[cls_start:cls_end]

    for block in method_blocks:
        name = re.match(r'%sdef (\w+)' % IND, block).group(1)
        pat = re.compile(r'\n?^    def %s\(.*?(?=\n    def |\nclass |\Z)' % re.escape(name),
                         re.MULTILINE | re.DOTALL)
        cls_body = pat.sub('', cls_body)

    # 插入点：before 方法（如 teardown_class）之前，否则类体末尾
    insert_at = len(cls_body)
    if before:
        bm = re.search(r'^%sdef %s\b' % (IND, re.escape(before)), cls_body, re.MULTILINE)
        if bm:
            insert_at = bm.start()
    new_body = (cls_body[:insert_at].rstrip('\n') + '\n\n' + '\n\n'.join(method_blocks) + '\n\n'
                + cls_body[insert_at:].lstrip('\n'))
    return content[:cls_start] + new_body + content[cls_end:]


def _methods_from_steps(steps):
    """步骤 → 需要生成的页面方法代码块列表（保持顺序，同名元素操作取最后一个）"""
    methods, seen = [], set()
    for s in steps:
        code = page_method_code(s)
        if not code:
            continue
        name = re.match(r'%sdef (\w+)' % IND, code).group(1)
        if name in seen:
            methods = [x for x in methods if not x.startswith(IND + 'def %s' % name)]
        seen.add(name)
        methods.append(code)
    return methods


def gen_page(page_file, steps, elements_file, desc='', page_class=None):
    """
    生成/追加页面对象文件 xxxPage.py。
    返回 {'ok': bool, 'action': 'created'|'updated'|'unchanged', 'content', 'msg'}
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.py$', page_file):
        return {'ok': False, 'msg': '页面文件名不合法（只允许字母/数字/下划线 + .py）'}
    page_class = page_class or element_library.to_class_name(page_file)
    elements_class = element_library.to_class_name(elements_file)
    path = os.path.join(PAGES_DIR, page_file)
    methods = _methods_from_steps(steps)

    if not os.path.exists(path):
        init_block = ('%sdef __init__(self, appOperator):\n'
                      '%sself.appOperator = appOperator\n'
                      '%sself._elements = %s()\n\n') % (IND, IND * 2, IND * 2, elements_class)
        body = init_block + '\n'.join(methods)
        cls_doc = desc or '页面对象（GUI 定位器生成）'
        content = ('# -*- coding: utf-8 -*-\n'
                   '# %s\n'
                   'from page_objects.app_ui.android.demoProject.elements.%s import %s\n\n\n'
                   'class %s:\n    """%s"""\n\n%s\n') % (
                       cls_doc,
                       os.path.splitext(elements_file)[0], elements_class,
                       page_class, cls_doc, body)
        _write(path, content)
        return {'ok': True, 'action': 'created', 'content': content,
                'msg': '已新建页面 %s（%s 个方法）' % (page_file, len(methods))}

    content = _read(path)
    existing = set(re.findall(r'^%sdef (\w+)' % IND, content, re.MULTILINE))
    # 工具方法已存在则跳过（实现固定）；元素操作方法同名覆盖
    to_add = []
    for code in methods:
        name = re.match(r'%sdef (\w+)' % IND, code).group(1)
        if name in existing and name in TOOL_METHODS:
            continue
        to_add.append(code)
    content = _ensure_elements_import(content, elements_file, elements_class)
    new_content = _upsert_class_method(content, page_class, to_add)
    action = 'updated' if new_content != content else 'unchanged'
    _write(path, new_content)
    return {'ok': True, 'action': action, 'content': new_content,
            'msg': '页面 %s 已更新（%s 个方法）' % (page_file, len(to_add))}


# ---------------------------------------------------------------------------
# 用例文件生成
# ---------------------------------------------------------------------------
def _test_method_block(method_name, steps, page_class):
    lines = ['%sdef %s(self):' % (IND, method_name),
             '%spage = self.page' % (IND * 2)]
    if not steps:
        lines.append('%spass' % (IND * 2))
    for i, s in enumerate(steps, 1):
        d = step_desc(s)
        line = case_step_line(s)
        lines.append('')
        lines.append('%s# %d. %s' % (IND * 2, i, d))
        if line:
            lines.append('%s%s' % (IND * 2, line))
        else:
            lines.append('%s# (此步骤为兜底/等待，无需调用代码)' % (IND * 2))
    return '\n'.join(lines) + '\n'


def _case_class_block(case_class, method_name, desc, pkg, activity, steps,
                      page_file, page_class, gen_teardown):
    lines = ['class %s:' % case_class, '',
             '%sdef setup_class(self):' % IND,
             '%s# is_need_kill_app=False：绕开 demo 客户端硬编码启动，显式启动被测 App' % (IND * 2),
             '%sself.demoProjectClient = APP_UI_Android_demoProject_Client(is_need_kill_app=False)' % (IND * 2),
             '%sself.appOperator = self.demoProjectClient.appOperator' % (IND * 2),
             "%sself.appOperator.start_activity('%s', '%s')" % (IND * 2, _escape(pkg), _escape(activity)),
             '%stime.sleep(3)' % (IND * 2),
             '%sself.page = %s(self.appOperator)' % (IND * 2, page_class),
             '',
             _test_method_block(method_name, steps, page_class).rstrip('\n')]
    if gen_teardown:
        lines += ['',
                  '%sdef teardown_class(self):' % IND,
                  '%sself.appOperator.reset_app()' % (IND * 2)]
    return '\n'.join(lines)


def gen_case(case_file, method_name, desc, pkg, activity, steps,
             page_file, page_class=None, case_class=None, gen_teardown=True):
    """
    生成/追加用例文件 test_xxx.py。
    返回 {'ok': bool, 'action': 'created'|'updated'|'added', 'content', 'msg'}
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.py$', case_file):
        return {'ok': False, 'msg': '用例文件名不合法（只允许字母/数字/下划线 + .py）'}
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', method_name):
        return {'ok': False, 'msg': '用例方法名不合法'}
    if not pkg or not activity:
        return {'ok': False, 'msg': '包名和 Activity 不能为空'}
    case_class = case_class or element_library.to_class_name(case_file)
    page_class = page_class or element_library.to_class_name(page_file)
    path = os.path.join(CASES_DIR, case_file)
    test_block = _test_method_block(method_name, steps, page_class)

    if not os.path.exists(path):
        lines = ['# -*- coding: utf-8 -*-',
                 '# %s' % (desc or 'GUI 定位器生成用例'),
                 '# 流程：']
        lines += ['# %d. %s' % (i, step_desc(s)) for i, s in enumerate(steps, 1)]
        lines += ['import time',
                  'from base.app_ui.android.demoProject.app_ui_android_demoProject_client '
                  'import APP_UI_Android_demoProject_Client',
                  'from page_objects.app_ui.android.demoProject.pages.%s import %s'
                  % (os.path.splitext(page_file)[0], page_class),
                  '',
                  '']
        lines.append(_case_class_block(case_class, method_name, desc, pkg, activity, steps,
                                       page_file, page_class, gen_teardown))
        content = '\n'.join(lines) + '\n'
        _write(path, content)
        return {'ok': True, 'action': 'created', 'content': content,
                'msg': '已新建用例 %s（%s）' % (case_file, method_name)}

    content = _read(path)
    if re.search(r'^class %s\b' % re.escape(case_class), content, re.MULTILINE):
        # 类已存在：类内追加/覆盖 test 方法（插到 teardown_class 前，setup/teardown 不动）
        new_content = _upsert_class_method(content, case_class, [test_block], before='teardown_class')
        action = 'updated'
    else:
        # 类不存在：文件末尾追加整个类（含 import 补全到文件头）
        need = 'from page_objects.app_ui.android.demoProject.pages.%s import %s' % (
            os.path.splitext(page_file)[0], page_class)
        if need not in content:
            content = need + '\n' + content
        block = _case_class_block(case_class, method_name, desc, pkg, activity, steps,
                                  page_file, page_class, gen_teardown)
        new_content = content.rstrip('\n') + '\n\n\n' + block + '\n'
        action = 'added'
    _write(path, new_content)
    return {'ok': True, 'action': action, 'content': new_content,
            'msg': '用例 %s 已%s %s' % (case_file, '更新' if action == 'updated' else '追加', method_name)}


# ---------------------------------------------------------------------------
# 用例文件快速追加（「添加元素」弹窗 → 保存并添加到用例）
# ---------------------------------------------------------------------------
def case_files_info():
    """返回 [{file, class, methods:[...]}]，供「目标用例」下拉（文件 + 方法两级联动）"""
    infos = []
    for f in list_case_files():
        p = os.path.join(CASES_DIR, f)
        if not os.path.exists(p):
            continue
        content = _read(p)
        cls = re.search(r'^class (\w+)', content, re.MULTILINE)
        methods = re.findall(r'^%sdef (\w+)\(' % IND, content, re.MULTILINE)
        infos.append({'file': f, 'class': cls.group(1) if cls else '', 'methods': methods})
    return infos


def append_code_to_method(case_file, method_name, step):
    """把 step 生成的一行调用代码追加到用例文件指定方法的末尾（不破坏文件结构）。

    step：统一步骤结构（type/element/param/desc），代码行 = case_step_line(step)。
    插入规则：目标方法体最后一个缩进行之后、下一个同级 def/@/class 之前。
    返回 {'ok': bool, 'action': 'appended', 'line': 代码行, 'content': 文件最新内容, 'msg'}
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.py$', case_file):
        return {'ok': False, 'msg': '用例文件名不合法（只允许字母/数字/下划线 + .py）'}
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', method_name):
        return {'ok': False, 'msg': '用例方法名不合法'}
    if not isinstance(step, dict) or step.get('type') not in STEP_TYPES:
        return {'ok': False, 'msg': '步骤结构不合法'}
    line = case_step_line(step)
    if not line:
        return {'ok': False, 'msg': '该操作类型没有可追加的代码行'}

    path = os.path.join(CASES_DIR, case_file)
    if not os.path.exists(path):
        return {'ok': False, 'msg': '用例文件 %s 不存在，请先到「📝 用例工作台」创建' % case_file}
    content = _read(path)

    m = re.search(r'^%sdef %s\(self\):' % (IND, re.escape(method_name)), content, re.MULTILINE)
    if not m:
        return {'ok': False, 'msg': '用例文件 %s 里没有方法 %s（先到「📝 用例工作台」创建该方法再追加）'
                                   % (case_file, method_name)}
    body_start = content.find('\n', m.end()) + 1
    if body_start <= 0:
        return {'ok': False, 'msg': '无法定位方法体'}

    tail = content[body_start:]
    nxt = re.search(r'\n%s(?:def |@|class )' % IND, tail)
    body_end = body_start + (nxt.start() + 1 if nxt else len(tail))
    body = content[body_start:body_end]

    new_body = body.rstrip('\n') + '\n' + IND * 2 + line + '\n\n'
    new_content = content[:body_start] + new_body + content[body_end:]
    _write(path, new_content)
    return {'ok': True, 'action': 'appended', 'line': line, 'content': new_content,
            'msg': '代码已追加到 %s::%s：%s' % (case_file, method_name, line)}


if __name__ == '__main__':
    import json
    import sys
    print('现有用例文件:', list_case_files())
    print('现有页面文件:', list_page_files())
    if len(sys.argv) > 1 and sys.argv[1] == 'demo':
        demo_steps = [
            {'type': 'click', 'element': 'btn_phone_login', 'param': '', 'desc': '点击手机号登录入口'},
            {'type': 'input', 'element': 'et_phone', 'param': '10000000000', 'desc': '输入手机号'},
            {'type': 'input', 'element': 'et_code', 'param': '8888', 'desc': '输入验证码'},
            {'type': 'assert_toast', 'element': '', 'param': '请先勾选下方协议', 'desc': '断言未勾选协议 toast'},
            {'type': 'screenshot', 'element': '', 'param': 'demo_登录', 'desc': '截图'},
            {'type': 'sleep', 'element': '', 'param': '2', 'desc': '等待 2 秒'},
        ]
        print('--- 生成页面 (demoLoginPage.py) ---')
        r = gen_page('demoLoginPage.py', demo_steps, 'locator_gui_elements.py', desc='演示登录页面')
        print(r['msg'], '| action:', r['action'])
        print(r['content'])
        print('--- 生成用例 (test_demo_login.py) ---')
        r2 = gen_case('test_demo_login.py', 'test_demo_login', '演示登录流程', 'com.recordlife.kuaige',
                      'com.recordlife.kuaige.feature.main.MainActivity', demo_steps,
                      'demoLoginPage.py', gen_teardown=True)
        print(r2['msg'], '| action:', r2['action'])
        print(r2['content'])
