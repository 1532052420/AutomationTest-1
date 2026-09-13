# -*- coding: utf-8 -*-
"""Web 执行平台 · 页面与 API 路由"""
import atexit
import os
import shutil
import re
import subprocess
import sys
import time
import urllib.request

from flask import Blueprint, jsonify, redirect, render_template, request, send_file

from web_platform import report_data
from generate_app_ui_test_report import inject_attachment_thumbnail_patch
from web_platform import runner
from web_platform.runtime_config import (
    BASE_DIR,
    WebPlatformConfig,
    adb_devices,
    check_appium,
    find_free_port,
    list_devices_conf_files,
    parse_devices_info,
    scan_case_tree,
)

bp = Blueprint('platform', __name__)

PLATFORM_CFG = WebPlatformConfig()

# 已启动的报告静态服务：run_id -> {'port': int, 'proc': Popen}（复用，避免重复起服务/进程泄漏）
_report_services = {}


@atexit.register
def _cleanup_report_services():
    """平台退出时终止全部报告静态服务与由本平台拉起的元素定位器，避免孤儿进程占用端口"""
    for svc in _report_services.values():
        try:
            svc['proc'].terminate()
        except Exception:
            pass
    loc = _locator_service.get('proc')
    if loc is not None:
        try:
            loc.terminate()
        except Exception:
            pass


# 由本平台拉起的元素定位器进程（平台重启后注册表为空，靠端口探测兜底）
_locator_service = {}


def _locator_up():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8001/api/status', timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _browser_host():
    """浏览器访问平台用的主机名/IP：跟随实际访问地址（本机访问=127.0.0.1，
    局域网同事用 IP 访问=同一个 IP），返回给浏览器的链接据此拼，避免写死 127.0.0.1。"""
    return (request.host or '').split(':')[0] or '127.0.0.1'


@bp.route('/api/locator/start', methods=['POST'])
def api_locator_start():
    """元素定位器智能启动：已运行直接返回；未运行则后台拉起并等就绪（前端按钮 loading 态）"""
    if _locator_up():
        return jsonify({'ok': True, 'url': 'http://%s:8001/' % _browser_host(), 'started': False})
    # 清理平台重启后注册表之外的残留进程，避免双实例抢端口
    subprocess.run(['pkill', '-f', 'element_locator/server.py'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    log_dir = os.path.join(BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = open(os.path.join(log_dir, 'element_locator.log'), 'a')
    try:
        proc = subprocess.Popen(
            [sys.executable, 'element_locator/server.py'], cwd=BASE_DIR,
            stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
    except Exception as e:
        log_file.close()
        return jsonify({'ok': False, 'msg': '启动元素定位器失败: %s' % e}), 500
    deadline = time.time() + 12
    while time.time() < deadline:
        if _locator_up():
            _locator_service['proc'] = proc
            log_file.close()
            return jsonify({'ok': True, 'url': 'http://%s:8001/' % _browser_host(), 'started': True})
        if proc.poll() is not None:
            log_file.close()
            return jsonify({'ok': False, 'msg': '元素定位器进程退出（查看 logs/element_locator.log）'}), 500
        time.sleep(0.3)
    proc.terminate()
    log_file.close()
    return jsonify({'ok': False, 'msg': '元素定位器启动超时（12 秒未就绪）'}), 500


# 用例节点白名单：文件路径/类/方法（pytest nodeid），杜绝 API 直调注入任意 pytest 参数
_NODE_RE = re.compile(r'^[A-Za-z0-9_\./:\u4e00-\u9fff-]+$')

# ---------------------------------------------------------------- 页面
@bp.route('/')
def page_index():
    return render_template('index.html')


@bp.route('/run')
def page_run():
    return render_template('run.html')


@bp.route('/runs/<run_id>')
def page_run_detail(run_id):
    return render_template('run_detail.html', run_id=run_id)


@bp.route('/report')
def page_report():
    return render_template('report.html')


@bp.route('/locator')
def page_locator():
    # 内嵌页：平台壳不销毁、iframe 加载定位器，替代 302 跨域整页跳转
    # （跨域跳转时浏览器「旧页销毁→新页首帧」的空档会铺一帧白画布，夜间模式下很刺眼）
    return render_template('locator.html')


# ---------------------------------------------------------------- API
@bp.route('/api/status')
def api_status():
    confs = list_devices_conf_files()
    adb = adb_devices()
    online = [d for d in adb['devices'] if d['state'] == 'device']
    appium_ok, appium_msg = check_appium('127.0.0.1', '4726')
    running = runner.manager.running_task()
    return jsonify({
        'ok': True,
        'service': 'app-ui-platform',
        'confs': confs,
        'device_online': len(online),
        'devices': adb['devices'],
        'appium': {'ok': appium_ok, 'msg': appium_msg},
        'running': running,
        'port': PLATFORM_CFG.port,
    })


@bp.route('/api/devices')
def api_devices():
    adb = adb_devices()
    running = runner.manager.running_task()
    used_udids = set()
    if running:
        used_udids.add(running['udid'])
    for d in adb['devices']:
        d['occupied'] = d['udid'] in used_udids and d['state'] == 'device'
    return jsonify({'ok': adb['ok'], 'msg': adb['msg'], 'devices': adb['devices']})


@bp.route('/api/cases')
def api_cases():
    return jsonify({'ok': True, 'tree': scan_case_tree()})


@bp.route('/api/confs')
def api_confs():
    confs = []
    for f in list_devices_conf_files():
        devices = parse_devices_info(f)
        confs.append({
            'file': f,
            'devices': [{
                'device_desc': d['device_desc'],
                'udid': (d.get('capabilities') or [{}])[0].get('udid', ''),
                'app_package': (d.get('capabilities') or [{}])[0].get('appPackage', ''),
                'server': '%s:%s' % (d['server_ip'], d['server_port']),
            } for d in devices],
        })
    return jsonify({'ok': True, 'confs': confs})


@bp.route('/api/exec_defaults')
def api_exec_defaults():
    """执行配置默认值：当前第一台在线设备(udid/型号) + 所选 conf 的默认 appPackage/appActivity。
    可选参数 ?conf=<文件> 指定默认值来源，缺省取第一个 conf。"""
    confs = list_devices_conf_files()
    conf_file = request.args.get('conf') or (confs[0] if confs else '')
    defaults = {'conf_file': conf_file, 'udid': '', 'model': '', 'app_package': '',
                'app_activity': '', 'server': '', 'appium_ok': False, 'occupied': False,
                'device_online': False, 'udid_from_conf': False}
    adb = adb_devices()
    online = [d for d in adb['devices'] if d['state'] == 'device']
    defaults['device_online'] = bool(online)
    if online:
        defaults['udid'] = online[0]['udid']
        defaults['model'] = online[0]['model']
    devices = parse_devices_info(conf_file) if conf_file else []
    if devices:
        d = devices[0]
        caps = (d.get('capabilities') or [{}])[0]
        defaults['app_package'] = caps.get('appPackage', '')
        defaults['app_activity'] = caps.get('appActivity', '')
        defaults['server'] = '%s:%s' % (d['server_ip'], d['server_port'])
        if not defaults['udid']:
            # 无在线设备时用 conf 里的 udid 预填输入框（仅作为默认值，不代表在线）
            defaults['udid'] = caps.get('udid', '')
            defaults['udid_from_conf'] = bool(defaults['udid'])
        defaults['appium_ok'], _ = check_appium(d['server_ip'], d['server_port'])
    running = runner.manager.running_task()
    defaults['occupied'] = bool(running)
    return jsonify({'ok': True, 'defaults': defaults, 'confs': confs})


@bp.route('/api/run', methods=['POST'])
def api_start_run():
    data = request.get_json(force=True, silent=True) or {}
    conf_file = (data.get('conf_file') or '').strip()
    case_nodes = data.get('case_nodes') or []
    case_nodes = [c for c in case_nodes if c and str(c).strip()]
    bad_nodes = [str(c) for c in case_nodes
                 if str(c).startswith('-') or '..' in str(c) or not _NODE_RE.match(str(c))]
    if bad_nodes:
        return jsonify({'ok': False, 'msg': '用例节点不合法: %s' % bad_nodes[0]}), 400
    overrides = data.get('overrides') or {}
    ok, result = runner.manager.start_run(conf_file, case_nodes, overrides)
    if not ok:
        return jsonify({'ok': False, 'msg': result}), 409 if '正在运行' in result else 400
    return jsonify({'ok': True, 'run_id': result})


@bp.route('/api/run/<run_id>')
def api_run_detail(run_id):
    task = runner.manager.get_task(run_id)
    if not task:
        return jsonify({'ok': False, 'msg': '任务不存在'}), 404
    return jsonify({'ok': True, 'task': task})


@bp.route('/api/run/<run_id>/log')
def api_run_log(run_id):
    offset = request.args.get('offset', 0, type=int)
    return jsonify(runner.manager.get_log(run_id, offset))


@bp.route('/api/run/<run_id>/cases')
def api_run_cases(run_id):
    """自建「用例执行记录」：解析 allure-results，返回用例+step+断言截图（不依赖 allure 命令行）"""
    results_dir = runner.manager.cli_results_dir(run_id)   # 命令行执行导入任务的目录
    return jsonify({'ok': True, 'cases': report_data.list_run_cases(run_id, results_dir)})


@bp.route('/api/runs/<run_id>/res/<path:source>')
def api_run_attachment(run_id, source):
    """alure-results 附件（断言截图）服务；source 严格限制在结果目录内，防路径穿越"""
    results_dir = runner.manager.cli_results_dir(run_id)
    p = report_data.resolve_attachment_path(run_id, source, results_dir)
    if not p:
        return jsonify({'ok': False, 'msg': '附件不存在'}), 404
    return send_file(p)


@bp.route('/api/run/<run_id>/video_thumbs')
def api_run_video_thumbs(run_id):
    """该次执行的失败录屏缩略图（首帧）：[{video, thumb}]，供报告列表直接展示与播放。
    缩略图由 ffmpeg 抽帧生成并缓存在 allure 数据目录内，走统一附件服务。"""
    results_dir = runner.manager.cli_results_dir(run_id) or report_data.run_results_dir(run_id)
    return jsonify({'ok': True, 'thumbs': report_data.ensure_video_thumbs(results_dir)})


@bp.route('/api/run/<run_id>/stop', methods=['POST'])
def api_stop_run(run_id):
    ok, msg = runner.manager.stop_run(run_id)
    return jsonify({'ok': ok, 'msg': msg}), 200 if ok else 400


@bp.route('/api/run/<run_id>/report', methods=['POST'])
def api_generate_report(run_id):
    """generate Allure 报告到 run/report/（不启动服务）"""
    ok, msg = runner.manager.generate_report(run_id)
    if not ok:
        return jsonify({'ok': False, 'msg': msg}), 400
    return jsonify({'ok': True, 'report_dir': msg})


@bp.route('/api/appium/start', methods=['POST'])
def api_appium_start():
    """启动 Appium 服务（127.0.0.1:4726）：已在运行直接返回；未运行则后台拉起并等服务就绪。
    与 ./run.sh start-appium 等价（供执行页「启动 Appium」按钮调用）。"""
    ok, msg = check_appium('127.0.0.1', '4726')
    if ok:
        return jsonify({'ok': True, 'msg': 'Appium 已在运行', 'already': True})
    appium_bin = os.path.expanduser('~/appium2/node_modules/.bin/appium')
    if not os.path.isfile(appium_bin):
        appium_bin = shutil.which('appium') or ''
    if not appium_bin or not os.path.isfile(appium_bin):
        return jsonify({'ok': False, 'msg': '未找到 appium 可执行文件（~/appium2）'}), 400
    # 端口竞态防护：4726 被占用但 /status 不通 = 僵死残留进程，先清理再拉起
    # （否则新进程 EADDRINUSE 直接退出，服务永远起不来）
    stale = subprocess.run(['pgrep', '-f', 'appium --port 4726'],
                           capture_output=True, text=True)
    if stale.returncode == 0 and stale.stdout.strip():
        subprocess.run(['pkill', '-f', 'appium --port 4726'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
    log_dir = os.path.join(BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log = open(os.path.join(log_dir, 'appium.log'), 'ab')
    # 关键：注入 ANDROID_HOME——uiautomator2 驱动建会话时必需；
    # 平台进程本身可能没有该环境变量（run.sh 才会 export），不注入会报
    # "Neither ANDROID_HOME nor ANDROID_SDK_ROOT environment variable was exported"
    sdk_root = os.environ.get('ANDROID_HOME') or os.path.expanduser('~/Library/Android/sdk')
    appium_env = dict(os.environ)
    appium_env.setdefault('ANDROID_HOME', sdk_root)
    appium_env.setdefault('ANDROID_SDK_ROOT', sdk_root)
    try:
        subprocess.Popen([appium_bin, '--port', '4726', '--address', '127.0.0.1',
                          '--base-path', '/wd/hub', '--log-level', 'info'],
                         stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True, cwd=BASE_DIR, env=appium_env)
    except Exception as e:
        return jsonify({'ok': False, 'msg': 'Appium 启动失败: %s' % e}), 500
    finally:
        log.close()
    # 异步模式：立即返回，由前端轮询 /api/status 等就绪（冷启动可能超过 20s，
    # 同步阻塞会让前端请求超时且无法感知"其实正在启动"）
    return jsonify({'ok': True, 'msg': 'Appium 启动中…'})


@bp.route('/api/run/<run_id>/report/open', methods=['POST'])
def api_open_report(run_id):
    """确保报告生成后起本地静态服务，**等服务就绪**再返回地址（前端拿到即可直接打开）。

    用 python -m http.server 替代 allure open：allure open 会自己拉起系统默认浏览器
    （浏览器里就出现"打开两个网页"），且起服务慢；allure 报告本身是纯静态站点，http.server 等价。
    同一 run 的服务复用（_report_services），重复点击不重复起进程。"""
    task = runner.manager.get_task(run_id)
    if not task:
        return jsonify({'ok': False, 'msg': '任务不存在'}), 404
    report_dir = runner.manager.report_dir_for(run_id)
    index_html = os.path.join(report_dir, 'index.html')
    # 未生成过则先生成；已生成也补一次缩略图补丁（历史报告/旧版本生成的可能没有）
    if not os.path.isfile(index_html):
        ok, msg = runner.manager.generate_report(run_id)
        if not ok:
            return jsonify({'ok': False, 'msg': msg}), 400
    else:
        inject_attachment_thumbnail_patch(report_dir)

    # 服务已在跑则直接复用
    svc = _report_services.get(run_id)
    if svc and svc['proc'].poll() is None:
        return jsonify({'ok': True, 'url': 'http://%s:%d/' % (_browser_host(), svc['port']), 'reused': True})
    if svc:
        _report_services.pop(run_id, None)

    # 清理同 run 遗留的旧服务进程（平台重启后注册表为空，但进程可能还在）
    subprocess.run(['pkill', '-f', 'http.server.*runs/%s/report' % run_id],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    port = find_free_port(PLATFORM_CFG.report_start_port)
    try:
        proc = subprocess.Popen(
            [sys.executable, '-m', 'http.server', str(port), '--directory', report_dir],
            cwd=report_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '启动报告服务失败: %s' % e}), 500

    # 轮询等服务真正可访问（最多 ~8 秒），就绪才返回，前端打开即有内容
    url = 'http://%s:%d/' % (_browser_host(), port)
    deadline = time.time() + 8
    last_err = ''
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    _report_services[run_id] = {'port': port, 'proc': proc}
                    return jsonify({'ok': True, 'url': url})
        except Exception as e:
            last_err = str(e)
        time.sleep(0.3)
    proc.terminate()
    return jsonify({'ok': False, 'msg': '报告服务启动超时: %s' % last_err}), 500


@bp.route('/api/runs')
def api_runs():
    return jsonify({'ok': True, 'runs': runner.manager.list_tasks()})


@bp.route('/api/runs/<run_id>', methods=['DELETE'])
def api_delete_run(run_id):
    if run_id.startswith('cli-'):
        # 命令行执行导入的记录：数据源在 output/app_ui，删除会把用户唯一的 allure 数据清掉
        return jsonify({'ok': False, 'msg': '命令行执行导入的记录不支持删除（数据源在 output/app_ui）'}), 400
    ok, msg = runner.manager.delete_run(run_id)
    return jsonify({'ok': ok, 'msg': msg}), 200 if ok else 400


@bp.route('/api/runs/clear', methods=['POST'])
def api_clear_runs():
    ok, msg = runner.manager.clear_runs()
    return jsonify({'ok': ok, 'msg': msg})