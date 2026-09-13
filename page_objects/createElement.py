from pojo.elementInfo import ElementInfo

class CreateElement:

    @classmethod
    def create(cls, locator_type, locator_value, expected_value=None, wait_type=None, wait_expected_value=None, wait_seconds=30, desc=None):
        elementInfo = ElementInfo()
        elementInfo.locator_type = locator_type
        elementInfo.locator_value = locator_value
        elementInfo.expected_value=expected_value
        elementInfo.wait_type=wait_type
        elementInfo.wait_seconds=wait_seconds
        elementInfo.wait_expected_value=wait_expected_value
        elementInfo.desc=desc   # 业务名称（可选）：报告步骤/日志优先显示，如「登录按钮」
        return elementInfo