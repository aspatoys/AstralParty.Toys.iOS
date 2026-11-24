"""AstralParty.Toys.iOS 的宿主层：pywebview 窗口 + 页面用的 js_api。

`gui.py` 只是入口；这里按页面职责分文件，装配在 `api.py`。
"""

from __future__ import annotations

from .api import Api
from .window import main

__all__ = ["Api", "main"]
