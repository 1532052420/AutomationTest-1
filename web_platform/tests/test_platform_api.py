# -*- coding: utf-8 -*-
"""AppUI 自动化测试平台 · 功能接口自动化测试

自包含：fixture 自动以 8099 端口拉起平台进程，结束后关闭。
运行：cd <项目根> && .venv/bin/python -m pytest web_platform/tests/ -v
用例与功能点映射见 web_platform/平台功能测试用例.md
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

PORT = int(os.environ.get('PLATFORM_TEST_PORT', '8099'))
BASE = 'http://127.0.0.1:%d' % PORT
VALID_CONF = 'config/demoProject/app_ui_android_devices_info_demoProject.conf'
VALID_CASE = 'cases/app_ui/android/demoProject/test_login.py::TestDemoToolLogin::test_phone_login_flow'
FAKE_RUN = '20991231_901'
RUNS_DIR = os.path.join(ROOT, 'output', 'runs')


def http(method, path, body=None, timeout=30, no_redirect=False):
    """返回 (status_code, body_str, headers)"""
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode('utf-8') if body is not None else None,
        headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(_NoRedirect) if no_redirect else urllib.request.build_opener()
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode('utf-8', 'replace'), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace'), dict(e.headers)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@pytest.fixture(scope='session')
def platform(tmp_path_factory):
    rec_path = tmp_path_factory.mktemp('dbg_records') / 'records.json'
    env = dict(os.environ, WEB_PLATFORM_PORT=str(PORT), PYTHONIOENCODING='utf-8',
               DEBUG_RECORDS_PATH=str(rec_path))
    proc = subprocess.Popen([sys.executable, os.path.join('web_platform', 'app.py')],
                            cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            code, _, _ = http('GET', '/api/status', timeout=3)
            if code == 200:
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError('测试平台启动超时')
    yield BASE
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.fixture()
def fake_run():
    """预置一条磁盘历史任务（模拟平台重启后的持久化恢复场景）"""
    run_dir = os.path.join(RUNS_DIR, FAKE_RUN)
    os.makedirs(os.path.join(run_dir, 'logs'), exist_ok=True)
    result = {'run_id': FAKE_RUN, 'status': 'RUNNING', 'start_time': '2099-12-31 00:00:00',
              'end_time': None, 'conf_file': VALID_CONF, 'device_desc': 'ghost', 'device_model': '',
              'app_package': 'com.example.app', 'udid': 'ghost-udid', 'overrides': {},
              'case_nodes': [VALID_CASE], 'total': 1, 'passed': 0, 'failed': 0, 'error': 0,
              'skipped': 0, 'exit_code': None, 'error_msg': '', 'allure_dir': '', 
              'log_path': 'output/runs/%s/logs/test.log' % FAKE_RUN, 'report_dir': '',
              'stop_requested': False}
    with open(os.path.join(run_dir, 'result.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False))
    yield FAKE_RUN
    shutil.rmtree(run_dir, ignore_errors=True)


# ---------------------------------------------------------------- 页面与导航
def test_pages_ok(platform):
    for page in ('/', '/run', '/report', '/debug'):
        code, body, _ = http('GET', page)
        assert code == 200, '%s -> %s' % (page, code)
        assert 'sidebar' in body


def test_locator_redirect(platform):
    code, _, headers = http('GET', '/locator', no_redirect=True)
    assert code == 302
    assert headers.get('Location') == 'http://127.0.0.1:8001/'


# ---------------------------------------------------------------- 只读探测
def test_status_structure(platform):
    code, body, _ = http('GET', '/api/status')
    assert code == 200
    d = json.loads(body)
    for key in ('ok', 'service', 'confs', 'device_online', 'devices', 'appium', 'running', 'port'):
        assert key in d, '缺字段 %s' % key
    assert d['service'] == 'app-ui-platform'
    assert isinstance(d['confs'], list) and d['confs']


def test_devices_structure(platform):
    code, body, _ = http('GET', '/api/devices')
    assert code == 200
    d = json.loads(body)
    assert d['ok'] is True and isinstance(d['devices'], list)


def test_cases_tree(platform):
    code, body, _ = http('GET', '/api/cases')
    assert code == 200
    tree = json.loads(body)['tree']
    assert tree, '用例树为空'
    node = tree[0]
    assert node['file'].startswith('cases/app_ui') and node['file'].endswith('.py')
    assert node['class_name'] and all(m.startswith('test_') for m in node['methods'])


def test_confs(platform):
    code, body, _ = http('GET', '/api/confs')
    assert code == 200
    confs = json.loads(body)['confs']
    assert confs and confs[0]['file'].endswith('.conf')
    assert 'devices' in confs[0]


def test_exec_defaults(platform):
    code, body, _ = http('GET', '/api/exec_defaults')
    assert code == 200
    d = json.loads(body)
    assert d['ok'] and d['defaults']['conf_file']
    for key in ('udid', 'app_package', 'app_activity', 'server', 'occupied'):
        assert key in d['defaults']
    # ?conf= 切换来源
    other = [c for c in d['confs'] if c != d['defaults']['conf_file']]
    if other:
        code2, body2, _ = http('GET', '/api/exec_defaults?conf=' + urllib.parse.quote(other[0]))
        assert code2 == 200 and json.loads(body2)['defaults']['conf_file'] == other[0]


# ---------------------------------------------------------------- 启动校验链
def test_start_run_empty_cases(platform):
    code, body, _ = http('POST', '/api/run', {})
    assert code == 400 and '请至少选择一个用例' in json.loads(body).get('msg', '')


def test_start_run_missing_conf(platform):
    code, body, _ = http('POST', '/api/run', {'case_nodes': [VALID_CASE]})
    assert code == 400 and '请选择设备配置文件' in json.loads(body).get('msg', '')


def test_start_run_bad_conf(platform):
    code, body, _ = http('POST', '/api/run', {'case_nodes': [VALID_CASE],
                                              'conf_file': 'config/demoProject/not_exist.conf'})
    assert code == 400 and '解析不到设备信息' in json.loads(body).get('msg', '')


def test_start_run_appium_down(platform):
    # 安全护栏：设备 + Appium 都在线时，此用例会真实创建执行任务驱动真机 —— 必须跳过
    st = json.loads(http('GET', '/api/status')[1])
    if st['appium']['ok'] and st['device_online'] > 0:
        import pytest
        pytest.skip('Appium 与设备均在线，跳过启动校验测试（避免驱动真实设备）')
    code, body, _ = http('POST', '/api/run', {'case_nodes': [VALID_CASE], 'conf_file': VALID_CONF})
    msg = json.loads(body).get('msg', '')
    # 无设备环境：Appium 未启动时应在 Appium 校验处拦截；若本机 Appium 恰好在跑，则应拦在设备在线校验
    assert code == 400 and ('Appium 不可用' in msg or '不在线' in msg), msg


def test_start_run_node_injection(platform):
    """用例节点白名单：pytest 参数注入必须被拒绝（TC-024）"""
    for bad in ('--version', '-k', 'x y', '../etc/passwd'):
        code, body, _ = http('POST', '/api/run',
                             {'case_nodes': [bad], 'conf_file': VALID_CONF})
        assert code == 400 and '用例节点不合法' in json.loads(body).get('msg', ''), '%s -> %s' % (bad, body)


# ---------------------------------------------------------------- 历史与恢复
def test_disk_task_visible(platform, fake_run):
    code, body, _ = http('GET', '/api/runs')
    assert code == 200
    ids = [r['run_id'] for r in json.loads(body)['runs']]
    assert fake_run in ids, '磁盘历史未恢复'
    code, body, _ = http('GET', '/api/run/%s' % fake_run)
    assert code == 200 and json.loads(body)['task']['run_id'] == fake_run


def test_ghost_running_normalized(platform, fake_run):
    """平台重启残留的 RUNNING 任务应归一为 ERROR（TC-041）"""
    code, body, _ = http('GET', '/api/run/%s' % fake_run)
    task = json.loads(body)['task']
    assert task['status'] == 'ERROR', '幽灵 RUNNING 未归一: %s' % task['status']
    assert '平台重启' in (task['error_msg'] or '')


def test_delete_run(platform, fake_run):
    code, body, _ = http('DELETE', '/api/runs/%s' % fake_run)
    assert code == 200 and json.loads(body)['ok']
    assert not os.path.isdir(os.path.join(RUNS_DIR, fake_run)), 'run 目录未删除'
    code, body, _ = http('GET', '/api/runs')
    assert fake_run not in [r['run_id'] for r in json.loads(body)['runs']]


def test_delete_invalid_id(platform):
    code, body, _ = http('DELETE', '/api/runs/abc')
    assert code == 400 and 'run_id 不合法' in json.loads(body).get('msg', '')


def test_clear_runs(platform, fake_run):
    code, body, _ = http('POST', '/api/runs/clear', {})
    assert code == 200 and json.loads(body)['ok']
    assert not os.path.isdir(os.path.join(RUNS_DIR, fake_run))


def test_not_found_paths(platform):
    code, body, _ = http('GET', '/api/run/99999999_999')
    assert code == 404 and '任务不存在' in json.loads(body).get('msg', '')
    code, body, _ = http('GET', '/api/run/99999999_999/log')
    assert code == 200 and json.loads(body)['ok'] is False
    code, body, _ = http('POST', '/api/run/99999999_999/stop', {})
    assert code == 400
    code, body, _ = http('POST', '/api/run/99999999_999/report', {})
    assert code == 400
    code, body, _ = http('POST', '/api/run/99999999_999/report/open', {})
    assert code == 404


def test_cases_of_missing_run(platform):
    code, body, _ = http('GET', '/api/run/99999999_999/cases')
    assert code == 200 and json.loads(body)['cases'] == []


def test_attachment_traversal_blocked(platform, fake_run):
    """附件接口路径穿越防护（TC-051）"""
    for evil in ('..%2F..%2Fconfig%2Fpytest.ini', '%2E%2E%2F%2E%2E%2Fetc%2Fpasswd',
                 '.hidden', 'sub%2Fx.png', 'nope.png'):
        code, _, _ = http('GET', '/api/runs/%s/res/%s' % (fake_run, evil))
        assert code == 404, '%s -> %s（应拒绝）' % (evil, code)


# ---------------------------------------------------------------- 代码审查回归
def test_debug_items(platform):
    code, body, _ = http('GET', '/api/debug/items')
    assert code == 200
    d = json.loads(body)
    assert d['ok'] and len(d['items']) >= 40 and not d['load_errors']


def test_debug_run_single(platform):
    code, body, _ = http('POST', '/api/debug/run', {'id': 'common.hamcrest'}, timeout=120)
    assert code == 200 and json.loads(body)['result']['status'] == 'PASS'
    code, body, _ = http('POST', '/api/debug/run', {'id': 'nope.nope'}, timeout=30)
    assert code == 200 and json.loads(body)['result']['status'] == 'FAIL'


# ---------------------------------------------------------------- 临时文件清理（单元级）
def test_tmp_device_files_cleanup():
    """任务终态后 config/app_ui_tmp/<pid>* 两个设备临时文件应被清理（TC-035）"""
    from web_platform import runner as R
    tmp_dir = R.APP_UI_TMP_DIR
    os.makedirs(tmp_dir, exist_ok=True)
    f1 = os.path.join(tmp_dir, str(os.getpid()))
    f2 = os.path.join(tmp_dir, '%s_current_desired_capabilities' % os.getpid())
    for f in (f1, f2):
        with open(f, 'w') as fh:
            fh.write('{}')
    task = {'status': 'PASSED', 'tmp_files': [f1, f2]}
    R.ExecutionManager()._cleanup_device_tmp_files(task)
    assert not os.path.exists(f1) and not os.path.exists(f2)


# ---------------------------------------------------------------- 周边脚本
def test_run_sh_no_dead_branch():
    """run.sh 不再引用不存在的 run_web_ui_test.py（TC-070）"""
    content = open(os.path.join(ROOT, 'run.sh'), encoding='utf-8').read()
    assert 'run_web_ui_test' not in content
    subprocess.run(['bash', '-n', os.path.join(ROOT, 'run.sh')], check=True)


# ---------------------------------------------------------------- 审查记录
def _make_results(passed=38, failed=2, skipped=2):
    results = []
    n = 0
    for status, count in (('PASS', passed), ('FAIL', failed), ('SKIP', skipped)):
        for _ in range(count):
            results.append({'id': 'case.%03d' % n, 'file': 'x.py', 'title': 't',
                            'status': status, 'detail': '', 'error': None, 'duration_ms': 1})
            n += 1
    return results


def test_debug_records_save_and_list(platform):
    for i in range(3):
        code, body, _ = http('POST', '/api/debug/records',
                             {'results': _make_results(passed=30 + i), 'duration_ms': 1000 + i})
        assert code == 200 and json.loads(body)['ok']
    code, body, _ = http('GET', '/api/debug/records')
    d = json.loads(body)
    assert d['ok'] and d['total'] == 3 and d['pages'] == 1
    newest = d['records'][0]
    assert newest['summary']['passed'] == 32, '应按时间倒序（最新在前）'
    assert 'results' not in newest, '列表载荷不应携带明细'


def test_debug_records_pagination(platform):
    for i in range(12):
        http('POST', '/api/debug/records', {'results': _make_results(), 'duration_ms': i})
    code, body, _ = http('GET', '/api/debug/records')
    d = json.loads(body)
    assert d['total'] == 15 and d['pages'] == 2 and len(d['records']) == 10
    code, body, _ = http('GET', '/api/debug/records?page=2')
    d2 = json.loads(body)
    assert len(d2['records']) == 5 and d2['page'] == 2


def test_debug_records_detail_and_delete(platform):
    code, body, _ = http('POST', '/api/debug/records', {'results': _make_results()})
    rid = json.loads(body)['record_id']
    code, body, _ = http('GET', '/api/debug/records/%s' % rid)
    rec = json.loads(body)['record']
    assert len(rec['results']) == 42 and rec['summary']['failed'] == 2
    code, body, _ = http('DELETE', '/api/debug/records/%s' % rid)
    assert code == 200 and json.loads(body)['ok']
    code, body, _ = http('GET', '/api/debug/records/%s' % rid)
    assert code == 404


def test_debug_records_validation(platform):
    code, body, _ = http('POST', '/api/debug/records', {'results': []})
    assert code == 400
    code, body, _ = http('GET', '/api/debug/records/bad..id')
    assert code == 400
    code, body, _ = http('GET', '/api/debug/records/no_such_id')
    assert code == 404

# ---------------------------------------------------------------- 交互调试工具
def _run_tool(tool, params):
    code, body, _ = http('POST', '/api/debug/tool', {'tool': tool, 'params': params}, timeout=120)
    return code, json.loads(body)


def test_tool_po_generate_and_save(platform):
    import re as _re
    params = {'page_class': 'DbgToolTestPage', 'page_desc': '调试套件测试页',
              'elements': [{'name': 'btn_ok', 'desc': '确认', 'action': 'click',
                            'locator_type': 'ID', 'locator_value': 'com.app:id/ok',
                            'wait_type': 'VISIBILITY_OF'}]}
    code, d = _run_tool('po_generate', params)
    data = d['result']['data']
    assert data['page_class'] == 'DbgToolTestPage' and 'class DbgToolTestPage' in data['page_code']
    assert 'class DbgToolTestElements' in data['elements_code']
    # 保存 → 文件落盘 → 再保存（未勾选覆盖）应被拒 → 勾选后成功 → 清理
    code, d = _run_tool('po_save', params)
    assert d['result']['ok'] and len(d['result']['data']['written']) == 2
    page_path = os.path.join(ROOT, data['page_path'])
    elem_path = os.path.join(ROOT, data['elements_path'])
    assert os.path.isfile(page_path) and os.path.isfile(elem_path)
    code, d = _run_tool('po_save', params)
    assert d['result']['ok'] is False and '覆盖' in d['result']['msg']
    params['force'] = True
    code, d = _run_tool('po_save', params)
    assert d['result']['ok']
    os.remove(page_path); os.remove(elem_path)


def test_tool_po_validation(platform):
    code, d = _run_tool('po_generate', {'page_class': 'bad_name', 'elements': []})
    assert d['result']['ok'] is False and '大驼峰' in d['result']['msg']
    code, d = _run_tool('po_generate', {'page_class': 'GoodPage', 'elements': []})
    assert d['result']['ok'] is False and '至少定义一个元素' in d['result']['msg']


def test_tool_bad_name(platform):
    code, body, _ = http('POST', '/api/debug/tool', {'tool': 'rm -rf', 'params': {}})
    assert code == 400

# ---------------------------------------------------------------- 框架自动识别
def test_debug_functions_catalog(platform):
    """方法目录自动识别：覆盖框架文件，新增/删除文件后清单自动增减"""
    code, body, _ = http('GET', '/api/debug/functions', timeout=60)
    assert code == 200
    d = json.loads(body)
    assert d['ok'] and d['total_files'] >= 30 and d['total_methods'] >= 100
    files = {f['file']: f for f in d['files']}
    assert 'common/dateTimeTool.py' in files, '框架文件未自动识别'
    entries = files['common/dateTimeTool.py']['entries']
    targets = [e['target'] for e in entries]
    assert 'common.dateTimeTool::DateTimeTool.strToTimeStamp' in targets
    # 参数签名来自源码反射
    st = next(e for e in entries if e['target'] == 'common.dateTimeTool::DateTimeTool.strToTimeStamp')
    names = [p['name'] for p in st['params']]
    assert names == ['str', 'str_format', 'is_with_millisecond']
    # 用例目录也在扫描范围
    assert any(f.startswith('cases/') for f in files)


def test_debug_call_real_method(platform):
    """方法调试：真实调用框架方法并返回结果"""
    code, body, _ = http('POST', '/api/debug/tool', {
        'tool': '__call__',
        'params': {'target': 'common.dateTimeTool::DateTimeTool.strToTimeStamp',
                   'args': {'str': '2026-01-02 03:04:05'}}}, timeout=60)
    d = json.loads(body)
    assert d['result']['ok']
    ret = d['result']['data']['return']
    assert ret['kind'] == 'json' and isinstance(ret['value'], int) and ret['value'] > 1767196800
    assert 'duration_ms' in d['result']['data']

    code, body, _ = http('POST', '/api/debug/tool', {
        'tool': '__call__',
        'params': {'target': 'common.strTool::StrTool.getStringWithLBRB',
                   'args': {'sourceStr': 'a<x>b', 'lbStr': '<', 'rbStr': '>'}}}, timeout=60)
    ret = json.loads(body)['result']['data']['return']
    assert ret['value'] == 'x'


def test_debug_call_error_paths(platform):
    """方法调试错误路径：缺必填参数/未知参数/不可实例化给明确提示"""
    code, body, _ = http('POST', '/api/debug/tool', {
        'tool': '__call__',
        'params': {'target': 'common.strTool::StrTool.getStringWithLBRB',
                   'args': {'sourceStr': 'a<x>b'}}}, timeout=60)
    d = json.loads(body)
    assert d['result']['ok'] is False and '缺少必填参数' in d['result']['msg']
    code, body, _ = http('POST', '/api/debug/tool', {
        'tool': '__call__',
        'params': {'target': 'common.strTool::StrTool.getStringWithLBRB',
                   'args': {'sourceStr': 'a', 'lbStr': '<', 'rbStr': '>', 'bogus': 1}}}, timeout=60)
    assert '未知参数' in json.loads(body)['result']['msg']
    code, body, _ = http('POST', '/api/debug/tool', {
        'tool': '__call__',
        'params': {'target': 'common.appium.appOperator::AppOperator.click',
                   'args': {'element': 'x'}}}, timeout=60)
    d = json.loads(body)
    assert d['result']['ok'] is False and '构造' in d['result']['msg']

def test_tool_text_assert(platform):
    code, d = _run_tool('text_assert', {'source': '订单金额：123.45 元', 'pattern': '金额：([0-9.]+)'})
    assert code == 200 and d['result']['ok']
    data = d['result']['data']
    assert data['matched'] and data['groups'] == ['123.45'] and data['hamcrest_is_match_by_regexp'] is True


def test_tool_element_build(platform):
    code, d = _run_tool('element_build', {'locator_type': 'ID', 'locator_value': 'com.app:id/btn',
                                          'wait_type': 'VISIBILITY_OF', 'wait_seconds': 10})
    data = d['result']['data']
    assert d['result']['ok'] and data['wait_seconds'] == 10
    assert "Locator_Type.ID" in data['code'] and 'Wait_By.VISIBILITY_OF' in data['code']
    code, d = _run_tool('element_build', {'locator_type': 'BAD', 'locator_value': 'x'})
    assert d['result']['ok'] is False and '不合法' in d['result']['msg']


def test_tool_http_request_local(platform):
    """HTTP 调试工具走本地临时服务（不依赖外网）"""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps({'ok': True, 'q': self.path}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        code, d = _run_tool('http_request', {
            'url': 'http://127.0.0.1:%d/ping?x=1' % srv.server_address[1], 'method': 'get'})
        data = d['result']['data']
        assert d['result']['ok'] and data['status_code'] == 200 and json.loads(data['body'])['ok'] is True
    finally:
        srv.shutdown()
        srv.server_close()

# ---------------------------------------------------------------- 元素定位器智能启动
def test_locator_smart_start(platform):
    """点击即启动：未运行则拉起并等就绪；已运行直接复用（TC-076）"""
    code, body, _ = http('POST', '/api/locator/start', {}, timeout=60)
    assert code == 200, body
    d = json.loads(body)
    assert d['ok'] and d['url'] == 'http://127.0.0.1:8001/'
    assert isinstance(d['started'], bool)
    # 再点一次：必定复用（不再重复拉起）
    code, body, _ = http('POST', '/api/locator/start', {}, timeout=30)
    d2 = json.loads(body)
    assert d2['ok'] and d2['started'] is False


def test_launcher_script_clean():
    """双击启动器语法与内容检查（TC-077）"""
    path = os.path.join(ROOT, '测试平台启动器.command')
    assert os.path.isfile(path)
    content = open(path, encoding='utf-8').read()
    assert 'web_platform/app.py' in content and 'element_locator/server.py' in content
    assert 'stop-platform' in content or 'pkill' in content
    subprocess.run(['bash', '-n', path], check=True)
