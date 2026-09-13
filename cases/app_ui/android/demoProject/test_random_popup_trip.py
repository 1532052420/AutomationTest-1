# -*- coding: utf-8 -*-
# 随机弹窗路径验证 · 一条用例 13 个步骤（元素由元素定位器采集入库 popupTripElements.py）
# 路径：登录(10293865678/8888+断言登录成功弹窗) → 我的 → 充值 → 返回 → 充值 → 返回
#       → 广场 → 消息 → 杀进程 → 我的 → 充值 → 返回 → 写歌
# 随机弹窗验证方式：正常操作触发，处理器轮询被动识别——遇到即截图挂 allure 并关闭，无断言
import time
import allure

from base.app_ui.android.demoProject.app_ui_android_demoProject_client import APP_UI_Android_demoProject_Client
from page_objects.app_ui.android.demoProject.pages.popupTripPage import PopupTripPage


class TestRandomPopupTrip:

    def setup_class(self):
        # is_need_kill_app=False：绕开 demo 客户端硬编码启动，显式启动被测 App
        self.demoProjectClient = APP_UI_Android_demoProject_Client(is_need_kill_app=False)
        self.appOperator = self.demoProjectClient.appOperator
        self.appOperator.start_activity('com.recordlife.kuaige',
                                        'com.recordlife.kuaige.feature.main.MainActivity')
        time.sleep(3)
        self.page = PopupTripPage(self.appOperator)
        # 前置：首启一次性弹窗处理（不算步骤，无弹窗快速跳过）
        self.page.deal_first_launch_dialogs()

    @allure.parent_suite('快歌APP自动化')
    @allure.suite('随机弹窗路径')
    @allure.title('随机弹窗路径全流程（登录→充值往返→页签→杀进程重启→写歌，被动验证随机弹窗）')
    def test_random_popup_trip(self):
        page = self.page

        # 1. 登录：输入账号/验证码 → 立即登录 → 断言登录成功弹窗
        page.input_login_phone('10293865678')
        page.input_login_code('8888')
        page.click_login_submit()
        page.assert_login_success_popup()

        # 2. 点击底部「我的」
        page.click_tab_mine()

        # 3. 点击左上角 icon 进入充值页面（第一次）
        page.open_recharge_page()

        # 4. 点击左上角返回到我的页面（第一次）
        page.back_to_previous()

        # 5. 再次进入充值页面（第二次）
        page.open_recharge_page()

        # 6. 点击左上角返回到我的页面（第二次）
        page.back_to_previous()

        # 7. 点击广场页面
        page.click_tab_square()

        # 8. 点击消息页面
        page.click_tab_message()

        # 9. 杀掉快歌 App 进程
        page.kill_app()

        # 10. 重新拉起后进入「我的」
        page.relaunch_and_open_mine()

        # 11. 进入充值页面（第三次）
        page.open_recharge_page()

        # 12. 点击左上角返回上一页
        page.back_to_previous()

        # 13. 点击底部写歌按钮（路径结束，随机弹窗由处理器被动截图关闭）
        page.click_btn_write_song()

    def teardown_class(self):
        self.appOperator.reset_app()
