# -*- coding: utf-8 -*-
"""代码调试 · 框架文件自动识别引擎

scan_functions(): 反射扫描框架模块（common/pojo/base/init/page_objects/cases），
输出每个文件的类与公开方法目录：真实参数名、必填/默认值、类型注解、文档首行。
供平台 /api/debug/functions 使用（模块总览的「自动识别文件」与方法目录数据源）。
"""
import importlib
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SCAN_ROOTS = ['common', 'pojo', 'base', 'init', 'page_objects', 'cases']
_catalog_cache = None


class CallError(Exception):
    """调用入参不合法或目标不可调用"""


def _iter_modules():
    for root in SCAN_ROOTS:
        base = os.path.join(ROOT, root)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for fn in sorted(filenames):
                if not fn.endswith('.py') or fn == '__init__.py':
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                dotted = rel[:-3].replace(os.sep, '.')
                yield rel.replace(os.sep, '/'), dotted


def _param_info(p):
    required = p.default is inspect.Parameter.empty and p.kind in (
        inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY)
    ann = ''
    if p.annotation is not inspect.Parameter.empty:
        ann = getattr(p.annotation, '__name__', None) or str(p.annotation)
    return {'name': p.name, 'required': required,
            'default': None if p.default is inspect.Parameter.empty else repr(p.default),
            'annotation': ann}


def _entry(file_rel, module, cls_name, name, kind, fn, ctor_params, instantiable):
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        sig = None
    params = []
    if sig:
        for pn, p in sig.parameters.items():
            if pn in ('self', 'cls'):
                continue
            if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            params.append(_param_info(p))
    doc = (inspect.getdoc(fn) or '').splitlines()[0] if inspect.getdoc(fn) else ''
    target = '%s::%s.%s' % (module, cls_name, name) if cls_name else '%s::%s' % (module, name)
    return {'target': target, 'cls': cls_name, 'name': name, 'kind': kind,
            'params': params, 'ctor_params': ctor_params, 'instantiable': instantiable, 'doc': doc}


def scan_functions(force=False):
    """返回 [{file, module, entries:[{target,cls,name,kind,params,ctor_params,instantiable,doc}]}]"""
    global _catalog_cache
    if _catalog_cache is not None and not force:
        return _catalog_cache
    catalog = []
    for file_rel, dotted in _iter_modules():
        entry = {'file': file_rel, 'module': dotted, 'error': '', 'entries': []}
        try:
            mod = importlib.import_module(dotted)
        except Exception as e:
            entry['error'] = '%s: %s' % (type(e).__name__, e)
            catalog.append(entry)
            continue
        for cls_name, cls in [(n, o) for n, o in vars(mod).items()
                              if inspect.isclass(o) and o.__module__ == dotted]:
            ctor_params = []
            try:
                init_sig = inspect.signature(cls.__init__)
                ctor_params = [_param_info(p) for pn, p in list(init_sig.parameters.items())[1:]]
            except (ValueError, TypeError):
                pass
            instantiable = all(not p['required'] for p in ctor_params)
            for mname, mobj in list(vars(cls).items()):
                if mname.startswith('_'):
                    continue
                if isinstance(mobj, classmethod):
                    e = _entry(file_rel, dotted, cls_name, mname, 'classmethod', mobj.__func__, ctor_params, instantiable)
                elif isinstance(mobj, staticmethod):
                    e = _entry(file_rel, dotted, cls_name, mname, 'staticmethod', mobj.__func__, ctor_params, instantiable)
                elif inspect.isfunction(mobj):
                    e = _entry(file_rel, dotted, cls_name, mname, 'method', mobj, ctor_params, instantiable)
                else:
                    continue
                entry['entries'].append(e)
        for fn_name, fn in [(n, o) for n, o in vars(mod).items()
                            if inspect.isfunction(o) and o.__module__ == dotted and not n.startswith('_')]:
            entry['entries'].append(_entry(file_rel, dotted, '', fn_name, 'function', fn, [], True))
        catalog.append(entry)
    _catalog_cache = catalog
    return catalog
