# -*- coding: utf-8 -*-
"""代码调试 · APP UI 链路 / 页面对象 / 用例收集检查项"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dbg_kit import check, Skip, assert_true, require_device_and_appium

class _StubAppOperator(object):
    """万能记录桩：任何方法调用都被记录并返回 'stub'，用于无设备时验证页面对象方法接线"""
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _recorder(*args, **kwargs):
            self.calls.append(name)
            return True
        if name.startswith('__'):
            raise AttributeError(name)
        return _recorder


@check('page_objects.locator_type', 'page_objects/app_ui/locator_type.py', '定位方式常量完整性（Appium 全部 16 种定位）')
def _():
    from page_objects.app_ui.locator_type import Locator_Type
    required = ['ID', 'XPATH', 'CLASS_NAME', 'ACCESSIBILITY_ID', 'ANDROID_UIAUTOMATOR',
                'CSS_SELECTOR', 'LINK_TEXT', 'TAG_NAME', 'NAME']
    missing = [a for a in required if not hasattr(Locator_Type, a)]
    assert_true(not missing, '缺少定位常量: %s' % missing)
    assert_true(Locator_Type.ID == 'id' and Locator_Type.XPATH == 'xpath', '常量取值异常')
    total = len([a for a in dir(Locator_Type) if not a.startswith('_')])
    return '共 %d 种定位方式，核心 9 种齐备' % total


@check('page_objects.wait_type', 'page_objects/app_ui/wait_type.py', '等待类型常量完整性')
def _():
    from page_objects.app_ui.wait_type import Wait_Type
    attrs = [a for a in dir(Wait_Type) if not a.startswith('_')]
    assert_true(len(attrs) >= 5, '等待类型常量过少: %r' % attrs)
    return '%d 种等待类型: %s' % (len(attrs), ', '.join(attrs[:6]))


@check('common.appium.appOperator', 'common/appium/appOperator.py', 'APP 操作器：公开 API 完整性 + 设备在线时的运行时探测')
def _():
    from common.appium.appOperator import AppOperator
    required = ['get', 'click', 'sendText', 'getText', 'tap', 'start_activity', 'is_displayed',
                'is_enabled', 'is_toast_visible', 'get_current_url', 'getTitle']
    missing = [m for m in required if not hasattr(AppOperator, m)]
    assert_true(not missing, '缺少公开方法: %s' % missing)
    from dbg_kit import adb_device_serials, appium_ok
    if not adb_device_serials() or not appium_ok():
        raise Skip('无在线设备/Appium（%d 方法 API 完整性已验证）；运行时行为请连接设备后通过平台执行用例验证' % len(required))
    return 'API 完整（%d 个核心方法），且检测到设备 + Appium 在线' % len(required)


@check('page_objects.kuaige_elements', 'page_objects/app_ui/android/demoProject/elements/kuaigeLoginElements.py',
       '快歌元素仓库：元素属性实例化')
def _():
    from page_objects.app_ui.android.demoProject.elements.kuaigeLoginElements import KuaigeLoginElements
    e = KuaigeLoginElements()
    required = ['btn_phone_login', 'et_phone', 'et_code', 'agree_protocol', 'btn_login']
    missing = [a for a in required if not hasattr(e, a)]
    assert_true(not missing, '缺少元素定义: %s' % missing)
    return '元素齐备: %s' % ', '.join(a for a in dir(e) if not a.startswith('_'))


@check('page_objects.demo_login_page', 'page_objects/app_ui/android/demoProject/pages/demoToolLoginPage.py',
       '页面对象方法接线（桩操作器验证：点击/输入路径走通）')
def _():
    from page_objects.app_ui.android.demoProject.pages.demoToolLoginPage import DemoToolLoginPage
    stub = _StubAppOperator()
    page = DemoToolLoginPage(stub)
    page.tap_xy(360, 768)
    page.click_btn_phone_login()
    page.input_et_phone('13800000000')
    page.input_et_code('123456')
    page.click_agree_protocol()
    page.click_btn_login()
    assert_true({'tap', 'click', 'sendText'} <= set(stub.calls), '方法未落到 appOperator: %r' % stub.calls)
    return '调用链 page → appOperator 正常，触发操作: %s' % ' → '.join(stub.calls)


@check('page_objects.kuaige_login_page', 'page_objects/app_ui/android/demoProject/pages/kuaigeLoginPage.py',
       '快歌登录页对象：方法接线（桩操作器验证）')
def _():
    from page_objects.app_ui.android.demoProject.pages.kuaigeLoginPage import KuaigeLoginPage
    stub = _StubAppOperator()
    page = KuaigeLoginPage(stub)
    page.tap_anywhere_to_trigger_login()
    page.click_phone_login()
    page.input_phone('13800000000')
    page.input_code('123456')
    page.check_agreement()
    page.click_login()
    assert_true(set(stub.calls) >= {'tap', 'click', 'sendText'}, '方法未落到 appOperator: %r' % stub.calls)
    page.assert_need_login_toast()
    page.assert_login_success()
    return '登录流程方法全部接通（含 toast/成功断言路径）: %s' % ' → '.join(stub.calls)


@check('base.app_ui.client_api', 'base/app_ui/android/demoProject/app_ui_android_demoProject_client.py',
       'APP 客户端：导入 + 构造签名（设备运行时验证走执行用例）')
def _():
    import inspect
    from base.app_ui.android.demoProject.app_ui_android_demoProject_client import APP_UI_Android_demoProject_Client
    sig = inspect.signature(APP_UI_Android_demoProject_Client.__init__)
    assert_true('is_need_kill_app' in sig.parameters, '缺少 is_need_kill_app 参数（用例显式启动 App 依赖它）')
    from base.app_ui.android.demoProject.app_ui_android_demoProject_read_config import APP_UI_Android_DemoProject_Read_Config
    assert_true(APP_UI_Android_DemoProject_Read_Config is not None, '配置读取器导入失败')
    return '客户端/配置读取器导入正常，构造签名含 is_need_kill_app' + \
        '（真实 session 建立需设备+Appium，请通过平台执行用例验证）'


@check('base.appui.runtime', 'base/app_ui/android/demoProject/app_ui_android_demoProject_client.py',
       'APP 客户端运行时：真实建立 Appium 会话（需设备在线，约 30-60 秒）')
def _():
    require_device_and_appium()
    from base.app_ui.android.demoProject.app_ui_android_demoProject_client import APP_UI_Android_demoProject_Client
    client = APP_UI_Android_demoProject_Client(is_need_kill_app=False)
    assert_true(client.appOperator is not None, 'appOperator 未构建')
    driver = getattr(client.appOperator, 'driver', None) or getattr(client, 'driver', None)
    session = driver.session_id if driver is not None else 'unknown'
    try:
        if driver is not None:
            driver.quit()
    except Exception:
        pass
    return 'Appium 会话建立成功 session=%s' % session


@check('cases.collect.api', 'cases/api/demoProject', 'API 用例 pytest 收集（≥1 条可收集）')
def _():
    out = subprocess.check_output(
        [sys.executable, '-m', 'pytest', '--collect-only', '-q', '-c', 'config/pytest.ini', 'cases/api/'],
        stderr=subprocess.STDOUT, timeout=120).decode('utf-8', 'replace')
    count = out.count('::')
    assert_true(count >= 1, 'API 用例收集数为 0\n%s' % out[-500:])
    return '收集到 %d 条 API 用例' % count


@check('cases.collect.app', 'cases/app_ui/android/demoProject', 'APP 用例 pytest 收集（≥1 条可收集）')
def _():
    out = subprocess.check_output(
        [sys.executable, '-m', 'pytest', '--collect-only', '-q', '-c', 'config/pytest.ini', 'cases/app_ui/'],
        stderr=subprocess.STDOUT, timeout=120).decode('utf-8', 'replace')
    count = out.count('::')
    assert_true(count >= 1, 'APP 用例收集数为 0\n%s' % out[-500:])
    return '收集到 %d 条 APP 用例' % count
