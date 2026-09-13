# -*- coding: utf-8 -*-
# 本文件由 GUI 元素定位器自动生成/维护
from page_objects.createElement import CreateElement
from page_objects.app_ui.locator_type import Locator_Type
from page_objects.app_ui.wait_type import Wait_Type as Wait_By


class XiegeElements:
    def __init__(self):
        self.tab_write_song = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnCompose', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 底部tab-写歌按钮
        self.btn_one_key_write = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnWriteNewSong', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 写歌页-一键写歌按钮（步骤1断言锚点）
        self.et_content_input = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/contentInput', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 一键写歌-灵感输入框（步骤2断言锚点/步骤3输入）
        self.btn_generate_song = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/generateTrack', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 一键写歌-生成歌曲按钮
        self.text_composing = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/composing', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 生成等待页-歌曲生成中标题
        self.text_composing_tips = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/composingTips', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 生成等待页-进度提示文案（如：正在为你解析歌词…1%）
        self.text_track_name = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/trackName', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=300)  # 生成成功弹窗-歌名《今天我是谁》（步骤6前置锚点，长等待兼容生成耗时）
        self.btn_play_now = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnPlay', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 生成成功弹窗-立即播放按钮（进入歌曲详情页）
        self.lyrics_area = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/lyrics', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 歌曲详情页-歌词展示区（步骤6断言锚点，歌曲页特有）
        self.btn_download = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnDownload', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 歌曲详情页-左下角下载按钮
        self.btn_publish = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnPublish', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6, desc='发布作品/确认发布按钮（歌曲页与发布编辑页同id）')  # 发布作品/确认发布按钮（歌曲页与发布编辑页同id）
        self.text_mp3_option = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tvAudio', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 下载弹窗-MP3文件选项（步骤7断言锚点）
        self.text_wav_option = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tvWav', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 下载弹窗-WAV文件选项（步骤7断言锚点）
        self.btn_mp3_download = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnAudio', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 下载弹窗-MP3文件下载按钮
        self.btn_wav_download = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnWav', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 下载弹窗-WAV文件下载按钮
        self.btn_video_download = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnVideo', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 下载弹窗-歌曲视频按钮（步骤12）
        self.text_save_success = CreateElement.create(Locator_Type.XPATH, '//*[@text=\'保存成功\']', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=30, desc='保存成功弹窗标题（步骤8/10/14轮询锚点，text定位避免与歌曲页tvTitle同名）')  # 保存成功弹窗标题（步骤8/10/14轮询锚点，text定位避免与歌曲页tvTitle同名）
        self.btn_save_confirm = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnOk', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 保存成功弹窗-确定按钮
        self.text_save_full = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tvFull', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6, desc='歌曲视频页-保存整首文本（步骤12断言锚点）')  # 歌曲视频页-保存整首文本（步骤12断言锚点）
        self.tab_save_full = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tabFull', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6, desc='歌曲视频页-保存整首选项卡（步骤13）')  # 歌曲视频页-保存整首选项卡（步骤13）
        self.btn_save_video = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnSave', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6, desc='歌曲视频页-保存视频按钮（步骤13/14）')  # 歌曲视频页-保存视频按钮（步骤13/14）
        self.text_video_saved = CreateElement.create(Locator_Type.XPATH, '//*[@text=\'视频已保存至相册\']', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=60, desc='视频保存成功弹窗文案「视频已保存至相册」（步骤14轮询锚点，长等待兼容视频渲染）')  # 视频保存成功弹窗文案「视频已保存至相册」（步骤14轮询锚点，长等待兼容视频渲染）
        self.btn_video_ok = CreateElement.create(Locator_Type.XPATH, '//*[@text=\'好的\']', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6, desc='视频保存成功弹窗-好的按钮（步骤15）')  # 视频保存成功弹窗-好的按钮（步骤15）
        self.et_song_title = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/etTitle', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6, desc='发布作品页-歌名输入控件（步骤16断言锚点）')  # 发布作品页-歌名输入控件（步骤16断言锚点）
        self.btn_first_publish_bean = CreateElement.create(Locator_Type.XPATH, '//*[@text=\'去领更多金豆\']', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=3, desc='分支判断-今日首次发布歌曲弹窗的去领更多金豆按钮（出现即分支A）')  # 分支判断-今日首次发布歌曲弹窗的去领更多金豆按钮（出现即分支A）
        self.btn_share_cancel = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnCancel', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=3, desc='分享面板-关闭按钮（与下载弹窗关闭同id，两个弹窗不同时出现）')  # 分享面板-关闭按钮（与下载弹窗关闭同id，两个弹窗不同时出现）
