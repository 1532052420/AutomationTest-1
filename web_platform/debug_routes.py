# -*- coding: utf-8 -*-
"""Web 执行平台 · 代码审查（框架调试）路由

纯增量蓝图：不改动 routes.py 的任何既有逻辑。
调试项定义与执行全部在独立的 代码调试/ 目录，本文件只负责：
- /debug            调试页面
- /api/debug/items  检查项清单（按文件分类由前端完成）
- /api/debug/run    单项执行（子进程隔离，复用 代码调试/dbg_run.py 的输出协议）
"""
import json
import os
import subprocess
import sys

from flask import Blueprint, jsonify, render_template, request

from web_platform.runtime_config import BASE_DIR

bp = Blueprint('debug', __name__)

DBG_DIR = os.path.join(BASE_DIR, '代码调试')
DBG_RUN = os.path.join(DBG_DIR, 'dbg_run.py')
MARK_RESULT = '__DBG_RESULT__'
# 单项上限：maven 依赖校验约 5s、JVM 冷启动约 2s，留足余量
RUN_TIMEOUT_SECONDS = 360


def _load_registry():
    """按文件路径加载 代码调试/dbg_registry.py（目录名为中文，不走包导入）"""
    import importlib.util
    path = os.path.join(DBG_DIR, 'dbg_registry.py')
    spec = importlib.util.spec_from_file_location('dbg_registry_%d' % id(request), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@bp.route('/debug')
def page_debug():
    return render_template('debug.html')


@bp.route('/api/debug/items')
def api_debug_items():
    reg = _load_registry()
    items = [{'id': s['id'], 'file': s['file'], 'title': s['title']} for s in reg.get_checks()]
    return jsonify({'ok': True, 'items': items, 'load_errors': reg.get_load_errors()})


@bp.route('/api/debug/run', methods=['POST'])
def api_debug_run():
    body = request.get_json(silent=True) or {}
    check_id = (body.get('id') or '').strip()
    if not check_id:
        return jsonify({'ok': False, 'msg': '缺少调试项 id'})
    try:
        proc = subprocess.run(
            [sys.executable, DBG_RUN, check_id],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS, cwd=BASE_DIR,
            env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    except subprocess.TimeoutExpired:
        return jsonify({'ok': True, 'result': {'id': check_id, 'file': '-', 'title': '-',
                                               'status': 'FAIL', 'detail': '',
                                               'error': '执行超时(>%ds)' % RUN_TIMEOUT_SECONDS,
                                               'duration_ms': RUN_TIMEOUT_SECONDS * 1000}})
    result = None
    for line in reversed((proc.stdout or '').splitlines()):
        if line.startswith(MARK_RESULT):
            result = json.loads(line[len(MARK_RESULT):])
            break
    if result is None:
        return jsonify({'ok': False, 'msg': '调试子进程无结果输出: %s' % ((proc.stderr or proc.stdout or '')[-300:])})
    return jsonify({'ok': True, 'result': result})
