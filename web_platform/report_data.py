# -*- coding: utf-8 -*-
"""解析 allure-results（allure-pytest 采集的原始 JSON），供平台自建「用例执行记录」视图。

不依赖 allure 命令行：直接读每个 *-result.json 的用例/步骤/附件，
截图由前端走 /api/runs/<run_id>/res/<source> 获取。
采集层（allure-pytest）保留——step 树、断言通过/失败截图都是它写进 JSON 的；
这里只负责把 JSON 变成平台页面能渲染的数据，Allure 报告生成/查看层不再需要。
"""
import glob
import json
import os

RUNS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'runs')

_IMG_TYPES = ('image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/bmp')


def run_results_dir(run_id):
    return os.path.join(RUNS_DIR, run_id, 'allure-results')


def _pick_images(attachments):
    """只挑图片附件（断言通过/失败截图）；log/stdout 等文本附件剔除（日志平台另有展示）"""
    if not attachments:
        return []
    out = []
    for a in attachments:
        source = a.get('source') or ''
        if not source or (a.get('type') or '') not in _IMG_TYPES:
            continue
        out.append({'name': a.get('name') or '', 'type': a.get('type') or '', 'source': source})
    return out


def _collect_step_images(steps):
    """沿 step 树收集图片附件，保持顺序（断言截图通常在最后）"""
    out = []

    def walk(s):
        out.extend(_pick_images(s.get('attachments')))
        for sub in s.get('steps', []):
            walk(sub)

    for s in steps:
        walk(s)
    return out


def list_run_cases(run_id, results_dir=None):
    """解析该 run 的用例明细：allure 每个用例一个 *-result.json。

    results_dir 为空时读 output/runs/<run_id>/allure-results（平台发起的执行）；
    命令行执行导入的任务传 CLI 的 report_data 目录。
    返回 [{name, full_name, status, start, stop, duration_ms, steps, screenshots, error_message}]。
    steps 为空说明是旧 run（step 包裹之前）——降级用 screenshots 直接展示断言截图。
    目录不存在/无数据返回 []，页面显示空态。
    """
    rdir = results_dir or run_results_dir(run_id)
    return list_cases_in_dir(rdir)


def list_cases_in_dir(rdir):
    """解析指定 allure-results 目录里的全部用例明细（结构同 list_run_cases 返回值）。"""
    if not rdir or not os.path.isdir(rdir):
        return []
    cases = []
    for fp in sorted(glob.glob(os.path.join(rdir, '*-result.json'))):
        try:
            with open(fp, encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            continue
        raw_steps = d.get('steps') or []
        steps = []
        for s in raw_steps:
            steps.append({
                'name': s.get('name') or '',
                'status': s.get('status') or 'unknown',
                'start': s.get('start'),
                'stop': s.get('stop'),
                'attachments': _pick_images(s.get('attachments')),
            })
        sd = d.get('statusDetails') or {}
        start = d.get('start') or 0
        stop = d.get('stop') or start
        cases.append({
            'name': d.get('name') or os.path.basename(fp),
            'full_name': d.get('fullName') or '',
            'status': d.get('status') or 'unknown',
            'start': start,
            'stop': stop,
            'duration_ms': max(0, stop - start),
            'steps': steps,
            'screenshots': _pick_images(d.get('attachments')) or _collect_step_images(raw_steps),
            'error_message': sd.get('message') or '',
        })
    return cases


def run_stats(results_dir):
    """聚合一次执行的证据数量：{shots: 截图总数, videos: 失败证据视频数}。
    视频即 conftest 失败四件套挂载的 failure_video 附件（存在 allure-results 内）；
    目录不存在返回 None（调用方显示 —）。"""
    if not results_dir or not os.path.isdir(results_dir):
        return None
    stats = {'shots': 0, 'videos': 0}

    def count_ats(ats):
        for a in ats or []:
            t = a.get('type') or ''
            if t in _IMG_TYPES:
                stats['shots'] += 1
            elif t == 'video/mp4' or (a.get('name') or '').startswith('failure_video'):
                stats['videos'] += 1

    def walk(steps):
        for s in steps or []:
            count_ats(s.get('attachments'))
            walk(s.get('steps'))

    for fp in glob.glob(os.path.join(results_dir, '*-result.json')):
        try:
            with open(fp, encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            continue
        raw_steps = d.get('steps') or []
        walk(raw_steps)
        count_ats(d.get('attachments'))
    return stats


def resolve_attachment_path(run_id, source, results_dir=None):
    """附件文件绝对路径；严格限制为 allure-results 目录内的纯文件名，防路径穿越。
    results_dir：命令行执行导入任务的 allure-results 目录（为空走平台 runs 目录）。"""
    rdir = os.path.realpath(results_dir or run_results_dir(run_id))
    # 只允许 uuid-attachment.png 这种纯文件名，杜绝 ../、子目录、隐藏文件
    if not source or '/' in source or '\\' in source or source.startswith('.'):
        return None
    p = os.path.realpath(os.path.join(rdir, source))
    if not p.startswith(rdir + os.sep):
        return None
    if not os.path.isfile(p):
        return None
    return p
