"""事件循环 —— 常驻 asyncio 循环：pymobiledevice3 是 asyncio 的，GUI 是线程模型。"""

from __future__ import annotations

import asyncio
import threading

class LoopRunner:
    """常驻 asyncio 事件循环（pymobiledevice3 需要 asyncio，GUI 是线程模型）。"""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._serve, name="cesium-loop", daemon=True).start()

    def _serve(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def call(self, coro, timeout: float = 1800):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)
