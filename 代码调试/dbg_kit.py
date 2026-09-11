# -*- coding: utf-8 -*-
"""代码调试 · 基础工具包

每个调试项 = 一个 (id, file, title, fn) 规格：
- id     唯一英文标识（平台调用/CLI 调用的主键）
- file   归属的框架文件（用于平台界面"按文件分类"展示）
- title  中文说明
- fn     无参可调用对象；正常返回 -> PASS（返回值作为详情）；抛 Skip -> SKIP；抛其他异常 -> FAIL

约定：调试项内 import 框架模块一律写在 fn 内部（延迟导入）——
注册列表保持轻量，且"模块能不能 import"本身就是被验证的行为之一。
本包完全独立于框架与平台，不反向修改任何框架文件。
"""
import os
import re
import subprocess
import time
import traceback
import urllib.request
from contextlib import contextmanager
from tempfile import mkdtemp


class Skip(Exception):
    """调试项因环境不满足而跳过（不算失败）"""


# 全部调试项登记处：@check 装饰即注册（dbg_registry 统一聚合）
_SPECS = []


def check(id, file, title):
    def deco(fn):
        spec = {'id': id, 'file': file, 'title': title, 'fn': fn}
        _SPECS.append(spec)
        return spec
    return deco


def run_check(spec):
    """执行单个调试项，返回结构化结果（永不抛异常）"""
    result = {
        'id': spec['id'], 'file': spec['file'], 'title': spec['title'],
        'status': 'PASS', 'detail': '', 'error': None, 'duration_ms': 0,
    }
    t0 = time.time()
    try:
        detail = spec['fn']()
        if detail is not None:
            result['detail'] = str(detail)
    except Skip as e:
        result['status'] = 'SKIP'
        result['detail'] = str(e)
    except Exception as e:
        result['status'] = 'FAIL'
        result['error'] = '%s: %s' % (type(e).__name__, e)
        result['detail'] = traceback.format_exc(limit=8)
    result['duration_ms'] = int((time.time() - t0) * 1000)
    return result


@contextmanager
def tmp_workdir(prefix='dbg_'):
    """临时工作目录（用完即删），供文件类调试项做读写演练"""
    d = mkdtemp(prefix=prefix)
    try:
        yield d
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def setup_java_home():
    """JVM 依赖项（验证码识别等）启动前兜底定位 JDK8，对齐 run.sh 的环境逻辑"""
    if os.environ.get('JAVA_HOME'):
        return
    try:
        out = subprocess.check_output(['/usr/libexec/java_home', '-v', '1.8'],
                                      stderr=subprocess.DEVNULL, timeout=10)
        java_home = out.decode().strip()
        if java_home:
            os.environ['JAVA_HOME'] = java_home
            return
    except Exception:
        pass
    fallback = os.path.expanduser('~/Library/Java/JavaVirtualMachines/jdk8u504-b01/Contents/Home')
    if os.path.isdir(fallback):
        os.environ['JAVA_HOME'] = fallback


def http_get(url, timeout=4):
    """GET 并返回 (status_code, body_str)；连接失败抛异常"""
    resp = urllib.request.urlopen(url, timeout=timeout)
    return resp.getcode(), resp.read().decode('utf-8', 'replace')


def http_get_json(url, timeout=4):
    import ujson
    code, body = http_get(url, timeout)
    return code, ujson.loads(body)


def platform_status(port):
    """探测本地平台 HTTP 接口。返回 (up: bool, data: dict|None)"""
    try:
        _, data = http_get_json('http://127.0.0.1:%d/api/status' % port, timeout=3)
        return True, data
    except Exception:
        return False, None


def appium_ok():
    try:
        code, body = http_get('http://127.0.0.1:4726/wd/hub/status', timeout=3)
        return code == 200
    except Exception:
        return False


def adb_device_serials():
    """当前在线的 adb 设备序列号列表（adb 不存在或无设备返回 []）"""
    adb = os.environ.get('ADB_BIN') or os.path.expanduser('~/Library/Android/sdk/platform-tools/adb')
    if not os.path.exists(adb):
        adb = 'adb'
    try:
        out = subprocess.check_output([adb, 'devices'], stderr=subprocess.DEVNULL, timeout=10)
        serials = []
        for line in out.decode('utf-8', 'replace').splitlines()[1:]:
            m = re.match(r'^(\S+)\tdevice\s*$', line.strip())
            if m:
                serials.append(m.group(1))
        return serials
    except Exception:
        return []


def require_device_and_appium():
    """设备强相关调试项的前置校验：不满足则 SKIP"""
    serials = adb_device_serials()
    if not serials:
        raise Skip('未检测到在线 Android 设备（adb devices 为空），跳过运行时验证；代码已通过导入/接口完整性检查')
    if not appium_ok():
        raise Skip('Appium 服务(4726)未启动，跳过运行时验证；代码已通过导入/接口完整性检查')
    return serials
