# -*- coding: utf-8 -*-
# 本文件由 GUI 元素定位器自动生成/维护
from page_objects.createElement import CreateElement
from page_objects.app_ui.locator_type import Locator_Type
from page_objects.app_ui.wait_type import Wait_Type as Wait_By


class PopupTripElements:
    def __init__(self):
        self.tab_square = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tabSquare', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 随机弹窗路径·底部广场tab
        self.tab_message = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tabMessage', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 随机弹窗路径·底部消息tab
        self.btn_write_song = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/btnCompose', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 随机弹窗路径·底部中间写歌按钮
        self.tab_mine = CreateElement.create(Locator_Type.ID, 'com.recordlife.kuaige:id/tabMine', wait_type=Wait_By.VISIBILITY_OF, wait_seconds=6)  # 随机弹窗路径·底部我的tab
