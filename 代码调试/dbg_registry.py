# -*- coding: utf-8 -*-
"""代码调试 · 检查项注册表

聚合所有 dbg_checks_* 模块的 CHECKS 列表，供 CLI（dbg_run.py）与平台（web_platform/debug_routes.py）使用。
import 失败的检查模块会被记录而不是炸掉整个注册过程（模块自身的问题也会在平台里以 FAIL 呈现）。
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# 供平台进程按文件路径加载本模块时能找到同目录的 dbg_kit / dbg_checks_*（CLI 已自行注入，幂等）
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_CHECK_MODULES = [
    'dbg_checks_a_common',
    'dbg_checks_b_http',
    'dbg_checks_c_pojo_base',
    'dbg_checks_d_appui',
    'dbg_checks_e_init',
]

# id -> spec；load_errors: [(module, error)]
_CHECKS = {}
_LOAD_ERRORS = []


def _load():
    if _CHECKS:
        return
    import dbg_kit
    for mod_name in _CHECK_MODULES:
        path = os.path.join(_HERE, mod_name + '.py')
        before = len(dbg_kit._SPECS)
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if len(dbg_kit._SPECS) == before:
                raise ValueError('模块未注册任何调试项')
        except Exception as e:
            _LOAD_ERRORS.append((mod_name, '%s: %s' % (type(e).__name__, e)))
            continue
        for item in dbg_kit._SPECS[before:]:
            if item['id'] in _CHECKS:
                raise ValueError('重复的检查项 id: %s' % item['id'])
            _CHECKS[item['id']] = item


def get_checks():
    """返回全部检查项规格列表（按文件名排序，保证平台分组展示稳定）"""
    _load()
    return sorted(_CHECKS.values(), key=lambda s: (s['file'], s['id']))


def get_check(check_id):
    _load()
    return _CHECKS.get(check_id)


def get_load_errors():
    _load()
    return list(_LOAD_ERRORS)


def summary():
    _load()
    files = {}
    for s in _CHECKS.values():
        files.setdefault(s['file'], []).append(s['id'])
    return {'total': len(_CHECKS), 'files': len(files), 'load_errors': _LOAD_ERRORS}
