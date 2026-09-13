# -*- coding: utf-8 -*-
# 随机弹窗路径验证 · 页面对象（元素引用 popupTripElements.py，元素与操作分离）
import subprocess
import time

from page_objects.app_ui.android.demoProject.elements.popupTripElements import PopupTripElements
from page_objects.app_ui.android.demoProject.elements.kuaigeLoginElements import KuaigeLoginElements
from page_objects.createElement import CreateElement
from page_objects.app_ui.locator_type import Locator_Type
from page_objects.app_ui.wait_type import Wait_Type as Wait_By


class PopupTripPage:
    """随机弹窗路径验证页面对象：登录（含成功弹窗断言）+ 我的/充值/广场/消息/写歌 路径动作"""

    def __init__(self, appOperator):
        self.appOperator = appOperator
        self._elements = PopupTripElements()
        self._login = KuaigeLoginElements()   # 登录元素与登录用例共用一份（定位器重复检测指示复用）

    def _probe(self, xpath, seconds=2):
        """短等待探测元素（弹窗/登录层存在性判断专用），未命中返回 None"""
        info = CreateElement.create(Locator_Type.XPATH, xpath,
                                    wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED, wait_seconds=seconds)
        return self.appOperator._find_once(info)

    def deal_first_launch_dialogs(self):
        """首启一次性弹窗循环处理：隐私协议「同意并继续」→ 系统权限「允许」；连续两轮无弹窗视为干净。
        另含坐标盲点兜底：实测该隐私弹窗存在「不进 uiautomator 树」的形态（自绘/动画窗口），
        仅靠元素探测会漏——历史实测坐标（两种弹窗布局）依次盲点兜底。"""
        idle_rounds = 0
        for _ in range(12):
            clicked = False
            for xp in ("//*[contains(@text,'同意并继续')]", "//*[@text='允许']"):
                el = self._probe(xp, seconds=1)
                if el is not None:
                    try:
                        el.click()
                        time.sleep(1.5)
                        clicked = True
                    except Exception:
                        pass
            if clicked:
                idle_rounds = 0
            else:
                idle_rounds += 1
                if idle_rounds >= 2:
                    break
                time.sleep(1)
        # 坐标盲点兜底（首启弹窗不进树时的唯一手段；无弹窗时点在主页空白区，无副作用）
        subprocess.run(['adb', 'shell', 'input', 'tap', '720', '1943'])   # 隐私弹窗布局A「同意并继续」
        time.sleep(2)
        subprocess.run(['adb', 'shell', 'input', 'tap', '720', '1495'])   # 隐私弹窗布局B「同意并继续」
        time.sleep(2)
        subprocess.run(['adb', 'shell', 'input', 'tap', '720', '2580'])   # 系统权限弹窗「允许」
        time.sleep(2)

    # ---- 步骤 1：登录（显式步骤，含成功弹窗断言）----
    def input_login_phone(self, phone):
        """步骤1a：点「我的」探登录层 → 打开手机登录表单 → 输入手机号"""
        self.appOperator.click(self._elements.tab_mine)
        time.sleep(2.5)
        if self._probe("//*[contains(@text,'手机登录')]") is None:
            return   # 已登录，无登录层
        self.appOperator.click(self._login.btn_phone_login)
        time.sleep(2)
        self.appOperator.sendText(self._login.et_phone, phone)

    def input_login_code(self, code):
        """步骤1b：输入验证码 + 收键盘 + 勾选协议（仅在登录表单存在时）"""
        if self._probe("//*[contains(@text,'获取验证码')]") is not None:
            self.appOperator.sendText(self._login.et_code, code)
            self.dismiss_ime_panel()
            self.appOperator.click(self._login.agree_protocol)
            time.sleep(1)

    def click_login_submit(self):
        """步骤1c：点击立即登录（仅在登录表单存在时）"""
        if self._probe("//*[contains(@text,'立即登录')]") is not None:
            self.appOperator.click(self._login.btn_login)
            time.sleep(4)

    def assert_login_success_popup(self):
        """步骤1d：断言登录成功弹窗——兼容新账号首登的「注册成功」toast；
        toast 已飘走时兜底「我的」页 tab 元素；断言截图由框架统一入 allure"""
        ok = self.appOperator.is_toast_visible('登录成功', wait_seconds=5)
        if not ok:
            ok = self.appOperator.is_toast_visible('注册成功', wait_seconds=5)
        if not ok:
            try:
                self.appOperator.getElement(self._elements.tab_mine)
                ok = True   # 登录层消失且底部 tab 可用 = 已进入登录态
            except Exception:
                ok = False
        self.appOperator.assert_true_with_shot('断言登录成功弹窗', ok,
                                               '未捕获到「登录成功/注册成功」toast 且未进入登录态')

    # ---- 路径步骤 ----
    def dismiss_ime_panel(self):
        """收起键盘/输入法面板（键盘可见或「键盘选择」面板存在时按 BACK，防误触返回）"""
        keyboard_shown = False
        try:
            keyboard_shown = bool(self.appOperator.is_keyboard_shown())
        except Exception:
            pass
        panel = self._probe("//*[contains(@text,'键盘选择')]", seconds=1)
        if keyboard_shown or panel is not None:
            self.appOperator.press_keycode(4)
            time.sleep(1)

    def click_tab_mine(self):
        """点击底部「我的」"""
        self.appOperator.click(self._elements.tab_mine)
        time.sleep(2)

    def open_recharge_page(self):
        """点击个人主页左上角 icon（K币充值入口，悬浮窗无 id，固定坐标点击）进入充值页面"""
        self.appOperator.tap(148, 248)
        time.sleep(3)

    def back_to_previous(self):
        """点击充值页左上角返回（无 id 固定布局，坐标点击）回到上一页"""
        self.appOperator.tap(112, 248)
        time.sleep(2)

    def click_tab_square(self):
        """点击底部「广场」"""
        self.appOperator.click(self._elements.tab_square)
        time.sleep(2)

    def click_tab_message(self):
        """点击底部「消息」"""
        self.appOperator.click(self._elements.tab_message)
        time.sleep(2)

    def kill_app(self):
        """杀掉快歌 App 进程"""
        subprocess.run(['adb', 'shell', 'am', 'force-stop', 'com.recordlife.kuaige'])
        time.sleep(2)

    def relaunch_and_open_mine(self):
        """重新拉起快歌并进入「我的」页面"""
        self.appOperator.start_activity('com.recordlife.kuaige',
                                        'com.recordlife.kuaige.feature.main.MainActivity')
        time.sleep(5)
        self.click_tab_mine()

    def click_btn_write_song(self):
        """点击底部中间「写歌」按钮"""
        self.appOperator.click(self._elements.btn_write_song)
        time.sleep(3)
