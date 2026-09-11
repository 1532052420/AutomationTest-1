# -*- coding: utf-8 -*-
"""FFmpeg 视频处理：失败证据视频裁剪。"""
import os
import subprocess

from common.video_evidence.config import find_tool


def probe_duration(path, ffprobe=None):
    """读取视频时长（秒），读不到返回 None。"""
    ffprobe = ffprobe or find_tool('ffprobe')
    if not ffprobe:
        return None
    r = subprocess.run(
        [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=30)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def crop_failure_video(raw_path, out_path, offset_seconds, before=5, after=5,
                       ffmpeg=None, ffprobe=None):
    """把原始录屏裁剪成 [offset-before, offset+after] 的失败证据视频。

    offset_seconds: 失败时刻相对录制起点的秒数（允许 ~1s 误差）。
    首选重编码（裁剪起点帧精确）；失败时兜底用 -c copy（关键帧对齐，起点可能有偏差）。
    """
    ffmpeg = ffmpeg or find_tool('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('未找到 ffmpeg 命令')
    duration = probe_duration(raw_path, ffprobe=ffprobe)
    if duration is None or duration <= 0:
        raise RuntimeError('无法读取视频时长: %s' % raw_path)
    start = max(0.0, offset_seconds - before)
    length = min(before + after, max(0.0, duration - start))
    if length <= 0.2:
        raise RuntimeError('视频长度 %.2fs 不足以裁剪出 %.2fs' % (duration, length))
    _ensure_parent(out_path)

    cmd = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
           '-i', str(raw_path), '-ss', '%.3f' % start, '-t', '%.3f' % length,
           '-map', '0:v:0', '-an',
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
           str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if _ok(out_path):
        return out_path

    cmd_copy = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
                '-ss', '%.3f' % start, '-i', str(raw_path),
                '-t', '%.3f' % length, '-c', 'copy', str(out_path)]
    r2 = subprocess.run(cmd_copy, capture_output=True, text=True, timeout=120)
    if _ok(out_path):
        return out_path
    raise RuntimeError('ffmpeg 裁剪失败: %s' % (r.stderr or r2.stderr).strip()[:300])


def _ok(path):
    return os.path.exists(str(path)) and os.path.getsize(str(path)) > 0


def _ensure_parent(path):
    parent = os.path.dirname(str(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
