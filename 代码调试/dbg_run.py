# -*- coding: utf-8 -*-
"""代码调试 · 运行器（CLI + 平台子进程入口）

用法：
    python 代码调试/dbg_run.py <check_id>    # 跑单个调试项
    python 代码调试/dbg_run.py all           # 全量（每项独立子进程，互不影响）

输出协议（供平台解析）：
    单项结束打印一行  __DBG_RESULT__{json}
    全量结束打印一行  __DBG_ALL__{json}
其余内容为人类可读过程信息。
"""
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)

MARK_ONE = '__DBG_RESULT__'
MARK_ALL = '__DBG_ALL__'
CHECK_TIMEOUT = 300  # 单项上限（秒）；maven/验证码识别/JVM 冷启动都在此之内


def _result_json(result):
    return MARK_ONE + json.dumps(result, ensure_ascii=False)


def run_single(check_id):
    import dbg_registry
    from dbg_kit import run_check
    spec = dbg_registry.get_check(check_id)
    if spec is None:
        result = {'id': check_id, 'file': '-', 'title': '未知调试项', 'status': 'FAIL',
                  'detail': '', 'error': 'id 不存在', 'duration_ms': 0}
    else:
        result = run_check(spec)
    print('[%s] %s · %s (%dms)' % (result['status'], result['id'], result['title'], result['duration_ms']))
    if result['detail']:
        print('  详情: %s' % result['detail'][:800].replace('\n', '\n  '))
    if result['error']:
        print('  错误: %s' % result['error'])
    print(_result_json(result))
    return 0 if result['status'] in ('PASS', 'SKIP') else 1


def run_all():
    import dbg_registry
    specs = dbg_registry.get_checks()
    load_errors = dbg_registry.get_load_errors()
    results = []
    print('=== 代码调试全量验证：%d 项（每项独立子进程）===' % len(specs))
    for spec in specs:
        try:
            proc = subprocess.run(
                [sys.executable, os.path.abspath(__file__), spec['id']],
                capture_output=True, text=True, timeout=CHECK_TIMEOUT, cwd=_ROOT,
                env=dict(os.environ, PYTHONIOENCODING='utf-8'))
            one = None
            for line in (proc.stdout or '').splitlines():
                if line.startswith(MARK_ONE):
                    one = json.loads(line[len(MARK_ONE):])
                    break
            if one is None:
                one = {'id': spec['id'], 'file': spec['file'], 'title': spec['title'],
                       'status': 'FAIL', 'detail': (proc.stdout or '')[-400:] + (proc.stderr or '')[-400:],
                       'error': '子进程无结果输出(可能超时 %ds)' % CHECK_TIMEOUT, 'duration_ms': 0}
        except subprocess.TimeoutExpired:
            one = {'id': spec['id'], 'file': spec['file'], 'title': spec['title'], 'status': 'FAIL',
                   'detail': '', 'error': '执行超时(>%ds)' % CHECK_TIMEOUT, 'duration_ms': CHECK_TIMEOUT * 1000}
        results.append(one)
        print('[%s] %s (%dms)%s' % (one['status'], one['id'], one['duration_ms'],
                                    '  ' + one['error'] if one.get('error') else ''))
    for mod_name, err in load_errors:
        results.append({'id': 'module.load.' + mod_name, 'file': mod_name, 'title': '检查模块自身导入',
                        'status': 'FAIL', 'detail': '', 'error': err, 'duration_ms': 0})
        print('[FAIL] 模块 %s 导入失败: %s' % (mod_name, err))
    passed = sum(1 for r in results if r['status'] == 'PASS')
    skipped = sum(1 for r in results if r['status'] == 'SKIP')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    print('=== 汇总: 共 %d 项，通过 %d，跳过 %d，失败 %d ===' % (len(results), passed, skipped, failed))
    print(MARK_ALL + json.dumps({'results': results, 'passed': passed, 'skipped': skipped,
                                 'failed': failed, 'total': len(results)}, ensure_ascii=False))
    return 0 if failed == 0 else 1


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    if arg == 'all':
        sys.exit(run_all())
    if not arg:
        import dbg_registry
        print('用法: python 代码调试/dbg_run.py <check_id|all>')
        for s in dbg_registry.get_checks():
            print('  %-42s %s (%s)' % (s['id'], s['title'], s['file']))
        sys.exit(0)
    sys.exit(run_single(arg))


if __name__ == '__main__':
    main()
