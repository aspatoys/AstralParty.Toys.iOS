"""页面用的 js_api 对象 —— 把各页面的 mixin 装成一个类交给 pywebview。

页面通过 `window.pywebview.api.*` 调用这里的方法。方法按页面职责拆在 `host/*_api.py`，
这里只保留装配与共享状态：pywebview 只认一个 js_api 对象，不能分多个对象注册。

只暴露方法：pywebview 会把 js_api 对象的公开属性也序列化给 JS，之前把一个 Window
挂在公开属性上，导致它去递归遍历 WebView2 的 .NET 对象图。
"""

from __future__ import annotations

import asyncio
import collections

import cesium_ios as engine

from .drop_api import DropApi
from .files_api import FilesApi
from .install_api import InstallApi
from .loop import LoopRunner
from .market_api import MarketApi
from .mods_api import ModsApi
from .session import SessionApi
from .skins_api import SkinsApi


class Api(SessionApi, ModsApi, FilesApi, SkinsApi, InstallApi, MarketApi, DropApi):
    """页面的宿主对象：方法按职责拆在 mixin 里，这里只放装配与共享状态。"""

    def __init__(self) -> None:
        self._loop = LoopRunner()
        self._lock = asyncio.Lock()
        self._lines: collections.deque[str] = collections.deque(maxlen=4000)
        self._task: dict = {"name": None, "running": False, "ok": None, "error": None}
        self._report: dict | None = None
        self._mods: list[dict] = []
        self._drops: collections.deque[dict] = collections.deque(maxlen=32)
        self._window = None
        self._device = None
        self._session = None
        engine.set_output_hook(self._lines.append)
