# 代码调试（代码审查）

独立于框架的调试与验证模块：把框架的接口、工具类、方法调用做成可一键执行的检查项，
用于快速验证"代码是否可用"。**本目录不修改框架任何文件**，平台侧接入也是纯增量
（`web_platform/debug_routes.py` 蓝图 + 一个页面）。

## 使用方式

### 1. 平台页面（推荐）

```bash
./run.sh platform        # 启动执行平台(:8080)
# 浏览器打开 http://127.0.0.1:8080/debug  → 侧边栏「🧪 代码审查」
```

- 按**文件分类**展示全部调试项，每项可单独「▶ 调试」
- 右上角「▶ 全部验证」逐项串行执行并实时刷新结果
- 结果状态：`PASSED`（通过）/ `FAILED`（失败，含错误与堆栈）/ `SKIPPED`（环境未就绪，如无设备、平台未启动）

### 2. 命令行

```bash
# 全量（每项独立子进程，互不影响）
.venv/bin/python 代码调试/dbg_run.py all

# 单项
.venv/bin/python 代码调试/dbg_run.py common.hamcrest

# 查看全部调试项
.venv/bin/python 代码调试/dbg_run.py
```

## 目录结构

| 文件 | 职责 |
| --- | --- |
| `dbg_kit.py` | 调试项基建：`@check` 注册、执行封装（PASS/FAIL/SKIP）、环境探测（adb/Appium/平台接口）、JDK 兜底 |
| `dbg_checks_a_common.py` | common 工具类（时间/文件/字符串/断言/网络/进程池/pytest 配置/Java jar/验证码/hamcrest） |
| `dbg_checks_b_http.py` | HTTP 客户端全方法（本地临时服务，不依赖外网）+ 两个平台与 Appium 的接口健康检查 |
| `dbg_checks_c_pojo_base.py` | pojo 数据类、base 配置读取器、接口客户端链路 |
| `dbg_checks_d_appui.py` | 定位/等待类型、页面对象接线（桩操作器）、APP 客户端、用例收集 |
| `dbg_checks_e_init.py` | init 初始化链路 + **全框架导入扫描**（89 个模块逐一 import） |
| `dbg_registry.py` | 检查项注册表（平台读取清单的入口） |
| `dbg_run.py` | 运行器：CLI 与平台子进程共用，输出带 `__DBG_RESULT__` / `__DBG_ALL__` 协议行 |

## 约定

- 新增调试项：在对应 `dbg_checks_*.py` 里加一个 `@check('id', '目标文件', '说明')` 函数，
  import 框架模块写在函数内部（延迟导入，"能不能 import"本身也是被验证的行为）
- 环境(*)未就绪的项抛 `Skip`，不计失败；真实失败必须给出可操作的错误信息
- 涉及进程/服务的初始化（http.server、mitmproxy）只做配置级验证，不重复拉起进程，
  避免与真实测试执行冲突
