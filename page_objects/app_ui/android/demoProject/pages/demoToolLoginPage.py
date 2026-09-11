# -*- coding: utf-8 -*-
# 工具生成·手机号登录流程执行验证
from page_objects.app_ui.android.demoProject.elements.kuaigeLoginElements import KuaigeLoginElements


class DemoToolLoginPage:
    """工具生成·手机号登录流程执行验证"""

    def __init__(self, appOperator):
        self.appOperator = appOperator
        self._elements = KuaigeLoginElements()

    def tap_xy(self, x, y):
        """点任意位置触发登录弹层"""
        self.appOperator.tap(x, y)

    def click_btn_phone_login(self):
        """点击手机号登录入口"""
        self.appOperator.click(self._elements.btn_phone_login)

    def input_et_phone(self, text):
        """输入手机号"""
        self.appOperator.sendText(self._elements.et_phone, text)

    def input_et_code(self, text):
        """输入验证码"""
        self.appOperator.sendText(self._elements.et_code, text)

    def assert_toast(self, text):
        """断言toast"""
        assert self.appOperator.is_toast_visible(text, wait_seconds=5), '断言toast「%s」' % text

    def assert_login_layer(self):
        """断言登录弹层已出现（手机登录入口可见）——新旧版本通用：旧版弹层前有'请先登录'toast，新版直接弹层"""
        self.appOperator.getElement(self._elements.btn_phone_login)

    def click_agree_protocol(self):
        """勾选我已阅读并同意"""
        self.appOperator.click(self._elements.agree_protocol)

    def click_btn_login(self):
        """再次点击立即登录"""
        self.appOperator.click(self._elements.btn_login)

    def assert_login_success(self):
        """断言登录成功：登录成功 toast 为主要依据（框架 is_toast_visible），
        toast 已完成生命周期时兜底页面文案（getElement）；成败截图由框架断言方法统一处理"""
        ok = self.appOperator.is_toast_visible('登录成功', wait_seconds=5)
        if not ok:
            try:
                self.appOperator.getElement(self._elements.text_login_success)
                ok = True
            except Exception:
                pass
        self.appOperator.assert_true_with_shot('断言登录成功', ok, '未捕获到「登录成功」toast 或页面文案')

    def wait_and_shot(self, tag):
        """截图存档"""
        import time
        time.sleep(1)
        self.appOperator.get_screenshot(tag)

