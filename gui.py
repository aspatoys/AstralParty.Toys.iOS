#!/usr/bin/env python3
"""AstralParty.Toys.iOS —— 图形界面（入口）。

    uv run gui.py
    ./start.ps1            # 先构建前端再启动（Windows）
    ./start.cmd            # 同上，双击即可

页面由 `webui/`（React + TypeScript + Vite）构建，产物在 `webui/dist/`。
设备操作全部复用 `cesium_ios/` 那一套（pymobiledevice3 + house_arrest），没有第二份实现。

线程模型：pywebview 是「主线程跑 GUI、JS 调用落到别的线程」，而 pymobiledevice3 是
asyncio 的。所以 `host/loop.py` 在后台拉一条常驻事件循环（`LoopRunner`），每次 JS 调用都
通过 `run_coroutine_threadsafe` 丢进去；长任务再放到独立线程，页面用 `drain()` 轮询日志与
任务状态 —— 不依赖从工作线程反向 push 到页面。

设备会话是**复用**的（`host/session.py` 的 `_ensure_device`）：house_arrest 每次建会话要
几百毫秒，逐次开关会让每次点击都迟钝。同一个 loop 上的多个协程会在 await 处交错，所以用
一把 `asyncio.Lock` 把设备操作串起来。

依赖声明在 `pyproject.toml`（含 pywebview），`uv run` 首次执行会自动建好 `.venv`。
"""

from __future__ import annotations

import sys

from host.window import main


if __name__ == "__main__":
    sys.exit(main())
