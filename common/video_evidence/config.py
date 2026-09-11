# -*- coding: utf-8 -*-
"""录屏与报告相关配置：环境变量优先，缺省用默认值。

环境变量：
    RECORDING_ENABLED        是否启用自动录屏（默认 true）
    RECORDING_REQUIRED       录屏启动失败是否终止测试（默认 false，只告警继续跑）
    RECORDING_KEEP_ON_SUCCESS 成功后是否保留原始视频（默认 false，删除）
    RECORDING_BEFORE_SECONDS 失败前保留秒数（默认 5）
    RECORDING_AFTER_SECONDS  失败后继续录制秒数（默认 5）
    ADB_SERIAL               指定设备序列号（缺省按用例设备信息，无则自动发现第一台在线设备）
    VIDEO_EVIDENCE_ROOT      录屏产物根目录（缺省为框架根目录，由 conftest 注入）
"""
import os
import shutil
import subprocess
from pathlib import Path

# PATH 找不到命令时再探测的常见安装位置（homebrew 等）
_FALLBACK_TOOL_DIRS = ('/opt/homebrew/bin', '/usr/local/bin')


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool_env(name, default):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


def find_tool(name):
    """定位外部命令：PATH 优先，再找常见安装位置(adb 另查 ANDROID_HOME)，找不到返回 None。"""
    path = shutil.which(name)
    if path:
        return path
    for d in _FALLBACK_TOOL_DIRS:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    if name == 'adb':
        android_home = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        if android_home:
            candidate = os.path.join(android_home, 'platform-tools', 'adb')
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def detect_first_device():
    """返回第一台在线设备的序列号，无设备/无 adb 返回 None。"""
    adb = find_tool('adb')
    if not adb:
        return None
    try:
        out = subprocess.run([adb, 'devices'], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            return parts[0]
    return None


class RecordingConfig:
    """一次运行共享的录屏配置。"""

    def __init__(self, adb_serial=None):
        self.enabled = _bool_env('RECORDING_ENABLED', True)
        self.required = _bool_env('RECORDING_REQUIRED', False)
        self.keep_on_success = _bool_env('RECORDING_KEEP_ON_SUCCESS', False)
        self.before_seconds = _int_env('RECORDING_BEFORE_SECONDS', 5)
        self.after_seconds = _int_env('RECORDING_AFTER_SECONDS', 5)
        # adb_serial 传入优先，其次 ADB_SERIAL 环境变量，最后自动发现
        self.adb_serial = adb_serial or os.environ.get('ADB_SERIAL') or detect_first_device()
        run_root = Path(os.environ.get('VIDEO_EVIDENCE_ROOT', os.getcwd()))
        # 产物统一放 output/ 下，随框架 .gitignore 的 *output* 规则被忽略
        self.tmp_dir = run_root / 'output' / 'video_evidence' / 'tmp'
        self.artifact_dir = run_root / 'output' / 'video_evidence' / 'artifacts'
        self.ffmpeg = find_tool('ffmpeg')
        self.ffprobe = find_tool('ffprobe')


def load_config(adb_serial=None):
    return RecordingConfig(adb_serial=adb_serial)
