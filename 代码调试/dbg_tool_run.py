# -*- coding: utf-8 -*-
"""代码调试 · 运行器（子进程入口，平台通过 stdin 传入参数）

输入（stdin JSON）:
  {"tool": "__call__", "params": {"target": "模块::类.方法", "ctor_args": {...}, "args": {...}}}  → 方法调试
  {"tool": "po_generate" | "po_save", "params": {...}}                                          → 新增 PO
输出: 人类可读行 + 最后一行协议标记 __DBG_TOOL__{json}
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)

MARK_TOOL = '__DBG_TOOL__'


def main():
    payload = json.loads(sys.stdin.read() or '{}')
    tool = payload.get('tool')
    params = payload.get('params') or {}
    from dbg_functions import CallError
    from dbg_tools import ToolError
    try:
        if tool == '__call__':
            from dbg_functions import call_function
            data = call_function(params.get('target'),
                                 params.get('ctor_args') or {}, params.get('args') or {})
            result = {'ok': True, 'data': data}
            print('[OK] call %s' % params.get('target'))
        else:
            from dbg_tools import TOOLS
            if tool not in TOOLS:
                raise ToolError('未知工具: %s' % tool)
            data = TOOLS[tool](params)
            result = {'ok': True, 'data': data}
            print('[OK] %s' % tool)
    except (ToolError, CallError) as e:
        result = {'ok': False, 'msg': str(e)}
        print('[输入错误] %s' % e)
    except Exception as e:
        import traceback
        result = {'ok': False, 'msg': '%s: %s' % (type(e).__name__, e),
                  'traceback': traceback.format_exc(limit=6)}
        print('[异常] %s: %s' % (type(e).__name__, e))
    print(MARK_TOOL + json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
