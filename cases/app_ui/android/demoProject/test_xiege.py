# -*- coding: utf-8 -*-
# 写歌·一键写歌全流程（生成 → 下载MP3/WAV → 保存视频 → 发布作品）
# 流程：
# 1. 点击底部【写歌】按钮，断言进入写歌页面（一键写歌存在）
# 2. 点击【一键写歌】，断言输入框可见
# 3. 输入灵感文字，断言输入框文本等于输入内容
# 4. 关闭输入法弹窗（收起键盘）
# 5. 点击【生成歌曲】，轮询最多5分钟直到生成完成
# 6. 断言成功进入歌曲详情页（歌词展示区存在）
# 7. 点击左下角【下载】，断言下载选项弹窗（MP3、WAV 可见）
# 8. 点击【MP3文件】，轮询等待「保存成功」弹窗
# 9. 点击【确定】关闭弹窗，断言弹窗消失
# 10. 点击下载【WAV文件】，等待1-2秒出现「保存成功」弹窗
# 11. 点击【确定】关闭弹窗，断言弹窗消失
# 12. 点击【歌曲视频】，断言切换到视频操作页（【保存整首】可见）
# 13. 点击【保存整首】，断言加载出【保存视频】按钮
# 14. 点击【保存视频】，循环轮询「视频已保存至相册」弹窗（超时失败）
# 15. 点击【好的】关闭弹窗，断言弹窗消失
# 16. 点击【发布作品】，断言进入发布编辑页（修改歌名控件存在）
# 17. 点击修改歌名控件进入编辑态
# 18. 关闭歌名编辑（真机验证：发布页右上角X是关闭整个发布页，故按返回键收起键盘），断言回到发布页
# 19. 点击【确认发布】触发发布流程
# 20. 分支判断：「今日首次发布歌曲」弹窗出现 → 点【去领更多金豆】；否则关闭「分享至」面板
# 21. 断言发布成功 toast（toast 短命，实际在步骤19点击后立即捕获，作品详情页元素兜底）
import time
import allure
from base.app_ui.android.demoProject.app_ui_android_demoProject_client import APP_UI_Android_demoProject_Client
from page_objects.app_ui.android.demoProject.pages.xiegePage import XiegePage


@allure.parent_suite('快歌APP自动化')
@allure.suite('写歌全流程')
class TestXiege:

    def setup_class(self):
        # is_need_kill_app=False：绕开 demo 客户端硬编码启动，显式启动被测 App
        self.demoProjectClient = APP_UI_Android_demoProject_Client(is_need_kill_app=False)
        self.appOperator = self.demoProjectClient.appOperator
        self.page = XiegePage(self.appOperator)

    @allure.title('写歌·一键写歌全流程（生成歌曲→下载→保存视频→发布作品）')
    def test_one_key_write_song_full_flow(self):
        page = self.page
        SONG_TEXT = '今天我是谁，谁是谁，你是谁'

        # 0. 回到主页面（统一用例起点）
        page.to_main_page()

        # 1. 点击底部【写歌】按钮，断言进入写歌页面
        page.click_tab_write_song()
        page.assert_btn_one_key_write()

        # 2. 点击【一键写歌】，断言输入框可见
        page.click_btn_one_key_write()
        page.assert_et_content_input()

        # 3. 输入灵感文字，断言输入框文本等于输入内容
        page.input_et_content_input(SONG_TEXT)
        page.assert_et_content_input_text(SONG_TEXT)

        # 4. 关闭输入法弹窗（收起键盘，无断言）
        page.dismiss_keyboard()

        # 5. 点击【生成歌曲】，轮询最多5分钟直到进入歌曲页（生成成功弹窗出现）
        page.click_btn_generate_song()
        page.wait_generate_done(timeout_seconds=300)

        # 6. 点击【立即播放】进入歌曲详情页，断言歌曲页特有元素（歌词展示区）存在
        page.click_btn_play_now()
        page.assert_lyrics_area()

        # 7. 点击左下角【下载】，断言下载选项弹窗弹出（MP3、WAV 选项可见）
        page.click_btn_download()
        page.assert_download_options()

        # 8. 点击【MP3文件】，轮询等待「保存成功」弹窗出现
        page.click_btn_mp3_download()
        page.wait_save_success(timeout_seconds=60)

        # 9. 点击【确定】关闭保存成功弹窗，断言弹窗消失
        page.click_btn_save_confirm()
        page.assert_save_success_gone()

        # 10. 重新打开下载弹窗点击【WAV文件】，等待1-2秒出现「保存成功」弹窗
        #     （真机验证：MP3保存成功点确定后下载弹窗一并关闭，WAV需重新打开）
        page.click_btn_download()
        page.click_btn_wav_download()
        time.sleep(2)
        page.wait_save_success(timeout_seconds=60)

        # 11. 点击【确定】关闭保存成功弹窗，断言弹窗消失
        page.click_btn_save_confirm()
        page.assert_save_success_gone()

        # 12. 重新打开下载弹窗点击【歌曲视频】，断言切换到视频操作页（【保存整首】可见）
        page.click_btn_download()
        page.click_btn_video_download()
        page.assert_text_save_full()

        # 13. 点击【保存整首】，断言页面加载出【保存视频】按钮
        page.click_tab_save_full()
        page.assert_btn_save_video()

        # 14. 点击【保存视频】，循环轮询「视频已保存至相册」弹窗（视频渲染耗时，超时则用例失败）
        page.click_btn_save_video()
        page.wait_video_saved(timeout_seconds=120)

        # 15. 点击【好的】关闭视频保存成功弹窗，断言弹窗关闭消失
        page.click_btn_video_ok()
        page.assert_video_saved_gone()

        # 16. 点击【发布作品】，断言进入发布作品编辑页面（修改歌名控件存在）
        page.click_btn_publish()
        page.assert_et_song_title()

        # 17. 点击修改歌名控件进入编辑态
        page.click_et_song_title()

        # 18. 关闭歌名编辑态，断言回到发布作品主页面（歌名控件仍可见）
        page.close_title_edit()
        page.assert_publish_page_back()

        # 19. 点击【确认发布】触发发布流程，并立即断言发布成功 toast
        #     （toast 存活仅 1.5~3.5s，必须在分支处理前捕获，作品详情页元素兜底）
        page.click_btn_confirm_publish()
        page.assert_publish_success_toast()

        # 20. 分支判断：出现「今日首次发布歌曲」弹窗 → 点【去领更多金豆】；
        #     弹窗不存在 → 关闭「分享至」面板回到作品页
        page.deal_after_publish()

    def teardown_class(self):
        # 不 reset_app：保留登录态与已发布作品，避免清数据后下次用例需重新登录
        self.appOperator.close_app()
