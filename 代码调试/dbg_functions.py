# -*- coding: utf-8 -*-
"""代码调试 · 框架方法调试引擎（调试对象 = 框架里真实存在的方法）

scan_functions(): 反射扫描框架模块（common/pojo/base/init/page_objects），
输出每个文件的类与公开方法目录：真实参数名、必填/默认值、类型注解、文档首行。

call_function(target, ctor_args, args):
- target 形如 "common.dateTimeTool::DateTimeTool.strToTimeStamp" 或 "模块::函数"
- classmethod/staticmethod 直接调用；实例方法先按源码签名构造实例（构造参数由用户填写，
  缺必填时明确报错），再调用
- 参数按源码注解/默认值类型做转换（int/float/bool/JSON 对象），空值 = 使用默认值
- 捕获方法内部 stdout，返回 {stdout, duration_ms, return}
"""
import contextlib
import importlib
import inspect
import io
import json
import os
import re
import sys
import time

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


def _coerce_args(func, args):
    """把用户输入（字符串为主）按源码签名转换；空值表示使用默认值"""
    sig = inspect.signature(func)
    out = {}
    for name, val in (args or {}).items():
        if name not in sig.parameters:
            raise CallError('未知参数: %s' % name)
        if val is None or (isinstance(val, str) and val.strip() == ''):
            continue
        p = sig.parameters[name]
        ann = p.annotation
        coerced = val
        ann_name = getattr(ann, '__name__', ann)
        default_is_num = isinstance(p.default, (int, float)) and not isinstance(p.default, bool)
        if ann is int or ann_name == 'int' or (ann is inspect.Parameter.empty and default_is_num and re_check_int(val)):
            try:
                coerced = int(str(val))
            except ValueError:
                raise CallError('参数 %s 需要整数，收到 %r' % (name, val))
        elif ann is float or ann_name == 'float' or (ann is inspect.Parameter.empty and isinstance(p.default, float)):
            try:
                coerced = float(str(val))
            except ValueError:
                raise CallError('参数 %s 需要数字，收到 %r' % (name, val))
        elif ann is bool or ann_name == 'bool':
            coerced = str(val).strip().lower() in ('1', 'true', 'yes', 'y')
        elif isinstance(val, str) and val.strip()[:1] in ('{', '['):
            try:
                coerced = json.loads(val)
            except Exception:
                coerced = val
        out[name] = coerced
    for name, p in sig.parameters.items():
        if name in ('self', 'cls'):
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if name not in out and p.default is inspect.Parameter.empty:
            raise CallError('缺少必填参数: %s' % name)
    return out


def re_check_int(val):
    import re as _re
    return bool(_re.match(r'^[+-]?\d+$', str(val).strip()))


def _serialize(result):
    try:
        json.dumps(result, ensure_ascii=False)
        return {'kind': 'json', 'type': type(result).__name__, 'value': result}
    except (TypeError, ValueError):
        text = repr(result)
        return {'kind': 'repr', 'type': type(result).__name__,
                'value': text[:6000] + ('…(截断)' if len(text) > 6000 else '')}


def call_function(target, ctor_args=None, args=None):
    """真实调用框架方法：target = "模块::类.方法" 或 "模块::函数" """
    if '::' not in str(target):
        raise CallError('target 格式应为 模块::类.方法 或 模块::函数')
    module_dotted, rest = str(target).split('::', 1)
    try:
        mod = importlib.import_module(module_dotted)
    except Exception as e:
        raise CallError('模块导入失败 %s: %s' % (module_dotted, e))
    buf = io.StringIO()
    t0 = time.time()
    if '.' in rest:
        cls_name, meth_name = rest.rsplit('.', 1)
        cls = getattr(mod, cls_name, None)
        if cls is None:
            raise CallError('类不存在: %s' % cls_name)
        mobj = vars(cls).get(meth_name)
        if mobj is None:
            raise CallError('方法不存在于 %s: %s（可能是继承方法）' % (cls_name, meth_name))
        if isinstance(mobj, classmethod):
            kwargs = _coerce_args(mobj.__func__, args)
            with contextlib.redirect_stdout(buf):
                result = getattr(cls, meth_name)(**kwargs)
        elif isinstance(mobj, staticmethod):
            kwargs = _coerce_args(mobj.__func__, args)
            with contextlib.redirect_stdout(buf):
                result = getattr(cls, meth_name)(**kwargs)
        else:
            ctor_kwargs = {}
            try:
                init_sig = inspect.signature(cls.__init__)
            except (ValueError, TypeError):
                init_sig = None
            for pn, p in list(init_sig.parameters.items())[1:] if init_sig else []:
                if pn in (ctor_args or {}) and str(ctor_args[pn]).strip() != '':
                    coerced = _coerce_args(cls.__init__, {pn: ctor_args[pn]})
                    ctor_kwargs.update(coerced)
                elif p.default is inspect.Parameter.empty:
                    raise CallError('构造 %s 需要参数 %s（请在「构造参数」中填写；'
                                    '若需要 driver 等运行时对象，该方法无法脱离设备调试）' % (cls_name, pn))
            instance = cls(**ctor_kwargs)
            kwargs = _coerce_args(getattr(cls, meth_name), args)
            with contextlib.redirect_stdout(buf):
                result = getattr(instance, meth_name)(**kwargs)
    else:
        func = getattr(mod, rest, None)
        if func is None:
            raise CallError('函数不存在: %s' % rest)
        kwargs = _coerce_args(func, args)
        with contextlib.redirect_stdout(buf):
            result = func(**kwargs)
    duration = int((time.time() - t0) * 1000)
    return {'target': target, 'stdout': buf.getvalue()[:2000], 'duration_ms': duration,
            'return': _serialize(result)}
