# -*- coding: utf-8 -*-
# 写歌全流程页面对象（元素定位器真机走查生成元素 + 流程辅助方法）
import time

from page_objects.createElement import CreateElement
from page_objects.app_ui.locator_type import Locator_Type
from page_objects.app_ui.wait_type import Wait_Type as Wait_By
from page_objects.app_ui.android.demoProject.elements.xiegeElements import XiegeElements


class XiegePage:
    """写歌模块交互用例页面对象：一键写歌 → 生成 → 下载/视频 → 发布"""

    def __init__(self, appOperator):
        self.appOperator = appOperator
        self._elements = XiegeElements()

    # ---- 统一入口 ----
    def to_main_page(self):
        """回到主页面（统一用例起点）：拉起主 Activity；若停留在二级页则逐级返回直到出现底部 tab"""
        self.appOperator.start_activity('com.recordlife.kuaige',
                                        'com.recordlife.kuaige.feature.main.MainActivity')
        time.sleep(2)
        probe = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tabHome',
                                     wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED, wait_seconds=2)
        for _ in range(4):
            try:
                self.appOperator.getElement(probe)
                break
            except Exception:
                self.appOperator.press_keycode(4)
                time.sleep(1)

    # ---- 步骤1：进入写歌页面 ----
    def click_tab_write_song(self):
        """点击底部【写歌】按钮"""
        self.appOperator.click(self._elements.tab_write_song)

    def assert_btn_one_key_write(self):
        """断言进入写歌页面（一键写歌按钮存在）"""
        self.appOperator.getElement(self._elements.btn_one_key_write)

    # ---- 步骤2：进入一键写歌输入页面 ----
    def click_btn_one_key_write(self):
        """点击【一键写歌】"""
        self.appOperator.click(self._elements.btn_one_key_write)

    def assert_et_content_input(self):
        """断言跳转至一键写歌输入页面（输入框可见）"""
        self.appOperator.getElement(self._elements.et_content_input)

    # ---- 步骤3：输入灵感文案 ----
    def input_et_content_input(self, text):
        """在输入框输入灵感文字"""
        self.appOperator.sendText(self._elements.et_content_input, text)

    def assert_et_content_input_text(self, expected):
        """断言输入框文本等于输入内容"""
        actual = self.appOperator.getText(self._elements.et_content_input)
        self.appOperator.assert_true_with_shot(
            '断言输入框文本等于输入内容', actual == expected,
            '输入框文本「%s」与期望「%s」不一致' % (actual, expected))

    # ---- 步骤4：收起输入法 ----
    def dismiss_keyboard(self):
        """关闭输入法弹窗（仅收起键盘，无断言）"""
        try:
            if self.appOperator.is_keyboard_shown():
                self.appOperator.hide_keyboard()
        except Exception:
            self.appOperator.press_keycode(4)
        time.sleep(1)

    # ---- 步骤5：生成歌曲并轮询等待（最多5分钟）----
    def click_btn_generate_song(self):
        """点击【生成歌曲】触发生成任务"""
        self.appOperator.click(self._elements.btn_generate_song)

    def wait_generate_done(self, timeout_seconds=300):
        """轮询等待生成完成：生成中提示消失、生成成功弹窗（歌名）出现为止。
        框架 getElement 自带随机弹窗扫描，长等待期间偶遇弹窗会被自动处理。"""
        step_no_desc = '轮询等待歌曲生成完成（最长%ds）' % timeout_seconds
        start = time.time()
        composing = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/composing',
                                         wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED, wait_seconds=1)
        deadline = start + timeout_seconds
        while time.time() < deadline:
            composing_gone = True
            try:
                self.appOperator.getElement(composing)
                composing_gone = False
            except Exception:
                composing_gone = True
            if composing_gone:
                try:
                    self.appOperator.getElement(self._elements.text_track_name)
                    self.appOperator.get_screenshot('歌曲生成完成')
                    return
                except Exception:
                    pass
            time.sleep(10)
        self.appOperator.assert_true_with_shot(step_no_desc, False,
                                               '等待%s秒后仍未进入歌曲页' % timeout_seconds)

    # ---- 步骤6：进入歌曲详情页 ----
    def click_btn_play_now(self):
        """点击生成成功弹窗【立即播放】进入歌曲详情页"""
        self.appOperator.click(self._elements.btn_play_now)

    def assert_lyrics_area(self):
        """断言成功进入歌曲详情页（歌词展示区存在，歌曲页特有元素）"""
        self.appOperator.getElement(self._elements.lyrics_area)

    # ---- 步骤7-11：下载 MP3 / WAV ----
    def click_btn_download(self):
        """点击左下角【下载】按钮"""
        self.appOperator.click(self._elements.btn_download)

    def assert_download_options(self):
        """断言下载选项弹窗弹出（MP3、WAV 选项可见）"""
        self.appOperator.getElement(self._elements.text_mp3_option)
        self.appOperator.getElement(self._elements.text_wav_option)

    def click_btn_mp3_download(self):
        """点击下载弹窗【MP3文件】"""
        self.appOperator.click(self._elements.btn_mp3_download)

    def click_btn_wav_download(self):
        """点击下载弹窗【WAV文件】"""
        self.appOperator.click(self._elements.btn_wav_download)

    def wait_save_success(self, timeout_seconds=60):
        """轮询等待「保存成功」弹窗出现"""
        probe = CreateElement.create(Locator_Type.XPATH, "//*[@text='保存成功']",
                                     wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED,
                                     wait_seconds=timeout_seconds)
        self.appOperator.getElement(probe)

    def click_btn_save_confirm(self):
        """点击【确定】关闭保存成功弹窗"""
        self.appOperator.click(self._elements.btn_save_confirm)

    def assert_save_success_gone(self):
        """断言保存成功弹窗已消失"""
        probe = CreateElement.create(Locator_Type.XPATH, "//*[@text='保存成功']",
                                     wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED, wait_seconds=2)
        gone = True
        try:
            self.appOperator.getElement(probe)
            gone = False
        except Exception:
            gone = True
        self.appOperator.assert_true_with_shot('断言保存成功弹窗消失', gone,
                                               '点击确定后「保存成功」弹窗仍存在')

    # ---- 步骤12-15：歌曲视频保存 ----
    def click_btn_video_download(self):
        """点击下载弹窗【歌曲视频】"""
        self.appOperator.click(self._elements.btn_video_download)

    def assert_text_save_full(self):
        """断言切换到歌曲视频操作页面（「保存整首」按钮可见）"""
        self.appOperator.getElement(self._elements.text_save_full)

    def click_tab_save_full(self):
        """点击【保存整首】"""
        self.appOperator.click(self._elements.tab_save_full)

    def assert_btn_save_video(self):
        """断言页面加载出【保存视频】按钮"""
        self.appOperator.getElement(self._elements.btn_save_video)

    def click_btn_save_video(self):
        """点击【保存视频】"""
        self.appOperator.click(self._elements.btn_save_video)

    def wait_video_saved(self, timeout_seconds=60):
        """循环轮询「视频已保存至相册」弹窗（视频渲染耗时，超时则失败）"""
        probe = CreateElement.create(Locator_Type.XPATH, "//*[@text='视频已保存至相册']",
                                     wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED,
                                     wait_seconds=timeout_seconds)
        self.appOperator.getElement(probe)

    def click_btn_video_ok(self):
        """点击【好的】关闭视频保存成功弹窗"""
        self.appOperator.click(self._elements.btn_video_ok)

    def assert_video_saved_gone(self):
        """断言视频保存成功弹窗关闭消失"""
        probe = CreateElement.create(Locator_Type.XPATH, "//*[@text='视频已保存至相册']",
                                     wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED, wait_seconds=2)
        gone = True
        try:
            self.appOperator.getElement(probe)
            gone = False
        except Exception:
            gone = True
        self.appOperator.assert_true_with_shot('断言视频保存成功弹窗关闭消失', gone,
                                               '点击好的后「视频已保存至相册」弹窗仍存在')

    # ---- 步骤16-18：发布作品编辑页 ----
    def click_btn_publish(self):
        """点击【发布作品】进入发布作品编辑页面"""
        self.appOperator.click(self._elements.btn_publish)

    def assert_et_song_title(self):
        """断言进入发布作品编辑页面（修改歌名控件存在）"""
        self.appOperator.getElement(self._elements.et_song_title)

    def click_et_song_title(self):
        """点击修改歌名控件进入编辑态（键盘弹起）"""
        self.appOperator.click(self._elements.et_song_title)

    def close_title_edit(self):
        """关闭歌名编辑态：按返回键收起键盘（真机验证：发布页右上角X会关闭整个发布页，
        不能用于关闭歌名编辑；BACK 在键盘显示时只收键盘不退出页面）"""
        self.appOperator.press_keycode(4)
        time.sleep(1.5)

    def assert_publish_page_back(self):
        """断言关闭歌名编辑态回到发布作品主页面（歌名控件仍可见）"""
        self.appOperator.getElement(self._elements.et_song_title)

    # ---- 步骤19-21：确认发布 ----
    def click_btn_confirm_publish(self):
        """点击【确认发布】触发发布流程"""
        self.appOperator.click(self._elements.btn_publish)

    def assert_publish_success_toast(self):
        """断言发布成功 toast 出现（toast 存活仅 1.5~3.5s，需在点击确认发布后立即调用）"""
        ok = self.appOperator.is_toast_visible('发布成功', wait_seconds=6)
        if not ok:
            # toast 已闪过时兜底：已进入发布成功后的作品详情页（作品标题可见）也算发布成功
            try:
                self.appOperator.getElement(CreateElement.create(
                    Locator_Type.ID, 'com.recordlife.kuaige:id/tvMusicTitle',
                    wait_type=Wait_By.PRESENCE_OF_ELEMENT_LOCATED, wait_seconds=10))
                ok = True
            except Exception:
                pass
        self.appOperator.assert_true_with_shot('断言发布成功toast出现', ok,
                                               '未捕获到「发布成功」toast 且未进入作品详情页')

    def deal_after_publish(self):
        """发布后分支处理：
        分支A：出现「今日首次发布歌曲」弹窗 → 点击【去领更多金豆】；
        分支B：弹窗不存在 → 关闭「分享至」面板回到作品页（确认发布后默认弹出分享面板）"""
        bean_visible = True
        try:
            self.appOperator.getElement(self._elements.btn_first_publish_bean)
        except Exception:
            bean_visible = False
        if bean_visible:
            self.appOperator.click(self._elements.btn_first_publish_bean)
        else:
            try:
                self.appOperator.click(self._elements.btn_share_cancel)
            except Exception:
                pass
