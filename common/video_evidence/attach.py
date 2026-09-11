# -*- coding: utf-8 -*-
"""Allure 附件挂载：失败视频 / 失败截图 / 文本。"""
import allure


def attach_video(path, name='failure_video'):
    allure.attach.file(str(path), name=name, attachment_type=allure.attachment_type.MP4)


def attach_screenshot(path, name='failure_screenshot'):
    allure.attach.file(str(path), name=name, attachment_type=allure.attachment_type.PNG)


def attach_text(content, name='failure_reason'):
    allure.attach(str(content), name=name, attachment_type=allure.attachment_type.TEXT)
