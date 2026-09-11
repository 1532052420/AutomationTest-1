# -*- coding: utf-8 -*-
"""APP UI 用例级自动录屏与失败证据包。

- 用例执行期间自动录屏（按设备能力选 adb screenrecord / screencap 抽帧兜底）
- 断言成功：断言截图照旧由 AppOperator.assert_true_with_shot 挂载，临时录屏清理
- 断言失败：按失败时刻裁剪 [T-5s, T+5s] 证据视频，连同失败截图、失败原因、
  录屏过程日志(含抽帧索引)一并挂入 allure
- 由 cases/app_ui/conftest.py 驱动，业务用例零侵入
"""
