#-*- coding:utf8 -*-
# 创建时间 2018/01/19 22:36
class ElementInfo:
    def __init__(self):
        self.locator_type=None
        self.locator_value=None
        self.expected_value=None
        self.wait_type=None
        self.wait_seconds=None
        self.wait_expected_value=None
        self.desc=None   # 业务名称（可选）：元素定位器「元素备注」填写后，报告步骤/日志优先显示它        self.desc=None
