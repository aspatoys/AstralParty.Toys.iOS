"""序列化工具 —— 把返回值里的 datetime 之类转成 JSON 能过的值。"""

from __future__ import annotations

import json

def jsonable(value):
    """pywebview 用 json.dumps 把返回值发给页面；遇到 datetime 之类会整条调用失败。"""
    return json.loads(json.dumps(value, default=str))
