# -*- coding: utf-8 -*-
"""
App 元素定位器 · Flask 服务入口（element_locator）
启动：cd ~/Desktop/AutomationTest && ./run.sh locator
默认地址：http://127.0.0.1:8001
技术方案与配置方法见同目录 技术实现方案.md
"""
import base64
import os
import re
import sys

from flask import Flask, jsonify, request, send_file

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import element_library
import case_generator
from tutorials import TUTORIALS, search_tutorials

app = Flask(__name__, static_folder='static', static_url_path='/static')

# 元素定位器版本号：每次功能/修复后递增，左上角会显示，用来确认本地是否已更新
APP_VERSION = 'v2.6'

# 开发工具要能"改完即刷"，静态文件禁用浏览器强缓存（Flask 默认 max-age=12h）
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


@app.after_request
def _no_cache(resp):
    resp.headers['Cache-Control'] = 'no-store'
    return resp

PORT = int(os.environ.get('LOCATOR_PORT', '8001'))


def _serialize(node, with_children=True):
    """节点 dict -> JSON 可序列化结构（_bounds/_center 转成普通字段）。
    with_children=False 用于 all 扁平列表：只保留节点自身，避免把整棵子树重复序列化（O(n²) 冗余）。"""
    d = {}
    for k, v in node.items():
        if k == '_bounds':
            d['bounds_num'] = list(v) if v else None
        elif k == '_center':
            d['center'] = list(v) if v else None
        elif k == 'children':
            if with_children:
                d['children'] = [_serialize(c) for c in v]
        elif k.startswith('_'):
            continue
        else:
            d[k] = v
    d.setdefault('children', [])
    return d


def _refresh_payload():
    """截图 + 元素树 完整载荷"""
    serial = device.get_device()
    if not serial:
        return None
    png = device.screenshot_png(serial)
    xml = device.dump_xml(serial)
    if not xml:
        return None
    try:
        data = device.xml_to_tree(xml)
    except Exception:
        return None
    # 为每个节点生成定位候选（ID/XPath/UIAutomator 等）
    for n in data['all']:
        n['locators'] = device.gen_locators(n, data['all'])
    return {
        'device': device.device_info(serial),
        'screenshot': 'data:image/png;base64,' + base64.b64encode(png).decode() if png else '',
        'width': data['width'],
        'height': data['height'],
        'tree': _serialize(data['tree']),
        'all': [_serialize(n, with_children=False) for n in data['all']],
    }


@app.route('/')
def index():
    return send_file(os.path.join(app.static_folder, 'index.html'))


@app.route('/api/status')
def api_status():
    serial = device.get_device()
    if not serial:
        return jsonify({'ok': False, 'version': APP_VERSION,
                        'msg': '未检测到已授权的 Android 设备，请连接手机并允许 USB 调试'})
    return jsonify({'ok': True, 'version': APP_VERSION, 'device': device.device_info(serial)})


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    payload = _refresh_payload()
    if not payload:
        return jsonify({'ok': False, 'msg': '刷新失败：请检查设备连接，或设备屏幕是否为亮屏状态'})
    return jsonify({'ok': True, **payload})


@app.route('/api/library')
def api_library():
    files = element_library.list_element_files()
    default = element_library.DEFAULT_FILE
    content = ''
    path = os.path.join(element_library.ELEMENTS_DIR, default)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    return jsonify({'ok': True, 'files': files, 'default': default, 'content': content})


@app.route('/api/add_element', methods=['POST'])
def api_add_element():
    data = request.get_json(silent=True) or {}
    # check_dup：默认 True 先做重复检测（库中已有相同定位 → 返回 duplicate 不落盘，前端决定用已有/新建）
    check_dup = data.get('check_dup', True)
    r = element_library.add_element(
        data.get('filename') or element_library.DEFAULT_FILE,
        data.get('name', '').strip(),
        data.get('locator_type', '').strip(),
        data.get('value', '').strip(),
        data.get('wait_type', 'VISIBILITY_OF').strip() or 'VISIBILITY_OF',
        check_dup=bool(check_dup),
    )
    return jsonify({'ok': r['ok'], 'msg': r.get('msg', ''), 'action': r.get('action', ''),
                    'duplicate': r.get('duplicate'),
                    'filename': data.get('filename') or element_library.DEFAULT_FILE,
                    'content': r.get('content', '')})


@app.route('/api/cases')
def api_cases():
    """列出现有用例文件（新建/追加下拉用）；case_info 含每个文件的方法列表（目标用例两级联动）"""
    return jsonify({'ok': True, 'cases': case_generator.list_case_files(),
                    'case_info': case_generator.case_files_info()})


@app.route('/api/add_code', methods=['POST'])
def api_add_code():
    """「保存并添加到用例」：把一步操作代码追加到目标用例文件的指定方法体末尾"""
    data = request.get_json(silent=True) or {}
    step = data.get('step') or {}
    if not isinstance(step, dict) or not step.get('type'):
        return jsonify({'ok': False, 'msg': '缺少操作步骤'})
    r = case_generator.append_code_to_method(
        data.get('case_file', '').strip(),
        data.get('method_name', '').strip(),
        step,
    )
    return jsonify({'ok': r['ok'], 'msg': r.get('msg', ''),
                    'action': r.get('action', ''),
                    'line': r.get('line', ''),
                    'case_file': data.get('case_file', '').strip(),
                    'method_name': data.get('method_name', '').strip(),
                    'content': r.get('content', '')})


@app.route('/api/pages')
def api_pages():
    """列出页面文件 + 各元素文件已定义的元素名（用例步骤下拉用）"""
    return jsonify({
        'ok': True,
        'pages': case_generator.list_page_files(),
        'elements': {f: element_library.list_element_names(f)
                     for f in element_library.list_element_files()},
    })


@app.route('/api/add_case', methods=['POST'])
def api_add_case():
    """生成/追加 用例文件（可选同时生成页面对象文件）"""
    data = request.get_json(silent=True) or {}
    steps = data.get('steps') or []
    if not isinstance(steps, list) or not steps:
        return jsonify({'ok': False, 'msg': '至少需要一个用例步骤'})
    # 校验步骤结构
    valid_types = set(case_generator.STEP_TYPES)
    for s in steps:
        if not isinstance(s, dict) or s.get('type') not in valid_types:
            return jsonify({'ok': False, 'msg': '步骤结构不合法：%r' % (s,)})

    r = case_generator.gen_case(
        data.get('case_file', '').strip(),
        data.get('method_name', '').strip(),
        data.get('desc', '').strip(),
        data.get('pkg', '').strip(),
        data.get('activity', '').strip(),
        steps,
        data.get('page_file', '').strip() or 'locator_gui_page.py',
        page_class=data.get('page_class', '').strip() or None,
        case_class=data.get('case_class', '').strip() or None,
        gen_teardown=bool(data.get('gen_teardown', True)),
    )
    if not r['ok']:
        return jsonify({'ok': False, 'msg': r.get('msg', '生成用例失败')})

    page_r = None
    if data.get('gen_page'):
        page_r = case_generator.gen_page(
            data.get('page_file', '').strip() or 'locator_gui_page.py',
            steps,
            data.get('elements_file', '').strip() or element_library.DEFAULT_FILE,
            desc=data.get('page_desc', '').strip() or data.get('desc', '').strip(),
            page_class=data.get('page_class', '').strip() or None,
        )
        if not page_r['ok']:
            return jsonify({'ok': False, 'msg': '用例已生成，但页面生成失败：%s' % page_r.get('msg')})

    return jsonify({
        'ok': True,
        'msg': r['msg'] + (('；页面 ' + page_r['msg']) if page_r else ''),
        'action': r['action'],
        'case': {'filename': data.get('case_file', '').strip(), 'content': r.get('content', '')},
        'page': {'filename': data.get('page_file', '').strip(), 'content': page_r.get('content', '')} if page_r else None,
    })


@app.route('/api/tap', methods=['POST'])
def api_tap():
    """设备真实点击（验证定位）：POST {x, y} 设备坐标"""
    serial = device.get_device()
    if not serial:
        return jsonify({'ok': False, 'msg': '未检测到设备'})
    data = request.get_json(silent=True) or {}
    x, y = data.get('x'), data.get('y')
    if x is None or y is None:
        return jsonify({'ok': False, 'msg': '缺少坐标 x/y'})
    ok = device.tap(serial, x, y)
    return jsonify({'ok': ok, 'msg': '已点击设备 (%d, %d)' % (x, y) if ok else '点击失败'})


@app.route('/api/tutorials')
def api_tutorials():
    q = request.args.get('q', '').strip()
    return jsonify({'ok': True, 'tutorials': search_tutorials(q)})


@app.route('/api/file_content')
def api_file_content():
    """顶部快速打开·查看文件内容（只读）：?case=<用例文件名> 或 ?element=<元素文件名>。
    目录由服务端拼接（用例→CASES_DIR，元素→ELEMENTS_DIR），文件名做白名单校验，防任意路径读取。"""
    case_file = (request.args.get('case') or '').strip()
    ele_file = (request.args.get('element') or '').strip()
    if bool(case_file) == bool(ele_file):
        return jsonify({'ok': False, 'msg': '请用 case 或 element 参数指定一个文件'})
    name_pat = re.compile(r'^[A-Za-z0-9_\-]+\.py$')
    if case_file:
        if not name_pat.match(case_file):
            return jsonify({'ok': False, 'msg': '用例文件名不合法'})
        full = os.path.join(case_generator.CASES_DIR, case_file)
        title = '%s（用例）' % case_file
    else:
        if not name_pat.match(ele_file):
            return jsonify({'ok': False, 'msg': '元素文件名不合法'})
        full = os.path.join(element_library.ELEMENTS_DIR, ele_file)
        title = '%s（元素库）' % ele_file
    if not os.path.isfile(full):
        return jsonify({'ok': False, 'msg': '文件不存在: %s' % os.path.basename(full)})
    try:
        with open(full, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return jsonify({'ok': False, 'msg': '读取失败: %s' % e})
    return jsonify({'ok': True, 'title': title, 'content': content})


if __name__ == '__main__':
    serial = device.get_device()
    if serial:
        print('已检测到设备: %s (%s)' % (serial, device.device_info(serial).get('model')))
    else:
        print('警告: 未检测到 Android 设备，界面将无法刷新截图（请连接手机后点"刷新"）')
    print('元素定位器已启动: http://127.0.0.1:%d/' % PORT)
    app.run(host='127.0.0.1', port=PORT, debug=False)