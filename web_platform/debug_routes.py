# -*- coding: utf-8 -*-
"""Web 执行平台 · 代码审查（框架调试）路由

纯增量蓝图：不改动 routes.py 的任何既有逻辑。
调试项定义与执行全部在独立的 代码调试/ 目录，本文件只负责：
- /debug            调试页面
- /api/debug/items  检查项清单（按文件分类由前端完成）
- /api/debug/run    单项执行（子进程隔离，复用 代码调试/dbg_run.py 的输出协议）
"""
import json
import math
import os
import re
import subprocess
import sys
import threading
import time

from flask import Blueprint, jsonify, render_template, request

from web_platform.runtime_config import BASE_DIR

bp = Blueprint('debug', __name__)

DBG_DIR = os.path.join(BASE_DIR, '代码调试')
DBG_RUN = os.path.join(DBG_DIR, 'dbg_run.py')
DBG_TOOL_RUN = os.path.join(DBG_DIR, 'dbg_tool_run.py')
MARK_RESULT = '__DBG_RESULT__'
MARK_TOOL = '__DBG_TOOL__'
# 单项上限：maven 依赖校验约 5s、JVM 冷启动约 2s，留足余量
RUN_TIMEOUT_SECONDS = 360
# 交互工具单次上限（HTTP 请求内部最长 45s）
TOOL_TIMEOUT_SECONDS = 90

# ---------------- 代码审查记录（每次「全部验证」保存一份快照，分页查询） ----------------
_RECORDS_PATH = os.environ.get('DEBUG_RECORDS_PATH') or os.path.join(
    BASE_DIR, 'output', 'debug_runs', 'records.json')
_RECORDS_LOCK = threading.Lock()
_RECORDS_MAX = 200     # 超出自动淘汰最旧记录
_RECORDS_PAGE = 10     # 每页条数
_RECORD_ID_RE = re.compile(r'^[A-Za-z0-9_]+$')


def _load_records():
    if not os.path.isfile(_RECORDS_PATH):
        return []
    try:
        with open(_RECORDS_PATH, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_records(records):
    os.makedirs(os.path.dirname(_RECORDS_PATH), exist_ok=True)
    with open(_RECORDS_PATH, 'w', encoding='utf-8') as f:
        f.write(json.dumps(records, ensure_ascii=False))


@bp.route('/api/debug/records', methods=['GET', 'POST'])
def api_debug_records():
    if request.method == 'POST':
        body = request.get_json(force=True, silent=True) or {}
        results = body.get('results') or []
        if not results:
            return jsonify({'ok': False, 'msg': '无结果可记录'}), 400
        summary = {
            'total': len(results),
            'passed': sum(1 for r in results if r.get('status') == 'PASS'),
            'failed': sum(1 for r in results if r.get('status') == 'FAIL'),
            'skipped': sum(1 for r in results if r.get('status') == 'SKIP'),
        }
        record = {
            'id': time.strftime('%Y%m%d_%H%M%S') + '_%03d' % (int(time.time() * 1000) % 1000),
            'time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_ms': int(body.get('duration_ms') or 0),
            'summary': summary,
            'results': results,
        }
        with _RECORDS_LOCK:
            records = _load_records()
            records.insert(0, record)
            _save_records(records[:_RECORDS_MAX])
        return jsonify({'ok': True, 'record_id': record['id'], 'summary': summary})
    # GET：分页列表（不带 results 明细，减小载荷）
    page = max(1, request.args.get('page', 1, type=int))
    with _RECORDS_LOCK:
        records = _load_records()
    total = len(records)
    pages = max(1, math.ceil(total / _RECORDS_PAGE))
    page = min(page, pages)
    items = [{'id': r['id'], 'time': r['time'], 'summary': r['summary'],
              'duration_ms': r.get('duration_ms', 0)} for r in records[(page - 1) * _RECORDS_PAGE: page * _RECORDS_PAGE]]
    return jsonify({'ok': True, 'records': items, 'page': page, 'pages': pages, 'total': total})


@bp.route('/api/debug/records/<record_id>', methods=['GET', 'DELETE'])
def api_debug_record(record_id):
    if not _RECORD_ID_RE.match(record_id or ''):
        return jsonify({'ok': False, 'msg': 'record_id 不合法'}), 400
    with _RECORDS_LOCK:
        records = _load_records()
        record = next((r for r in records if r.get('id') == record_id), None)
        if record is None:
            return jsonify({'ok': False, 'msg': '记录不存在'}), 404
        if request.method == 'DELETE':
            records = [r for r in records if r.get('id') != record_id]
            _save_records(records)
            return jsonify({'ok': True, 'msg': '已删除记录 %s' % record_id})
    return jsonify({'ok': True, 'record': record})


# ---------------- 交互式调试工具（用户填参数 → 子进程执行 → 返回数据） ----------------
@bp.route('/api/debug/tool', methods=['POST'])
def api_debug_tool():
    body = request.get_json(force=True, silent=True) or {}
    tool = str(body.get('tool') or '').strip()
    params = body.get('params') or {}
    if not re.match(r'^[a-z_]+$', tool or ''):
        return jsonify({'ok': False, 'msg': '工具名不合法'}), 400
    try:
        proc = subprocess.run(
            [sys.executable, DBG_TOOL_RUN],
            input=json.dumps({'tool': tool, 'params': params}, ensure_ascii=False),
            capture_output=True, text=True, timeout=TOOL_TIMEOUT_SECONDS, cwd=BASE_DIR,
            env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'msg': '工具执行超时(>%ds)' % TOOL_TIMEOUT_SECONDS})
    result = None
    for line in reversed((proc.stdout or '').splitlines()):
        if line.startswith(MARK_TOOL):
            result = json.loads(line[len(MARK_TOOL):])
            break
    if result is None:
        return jsonify({'ok': False, 'msg': '工具无输出: %s' % ((proc.stderr or proc.stdout or '')[-300:])})
    return jsonify({'ok': True, 'result': result})


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
