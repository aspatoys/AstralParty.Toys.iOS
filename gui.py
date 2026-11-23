#!/usr/bin/env python3
"""CesiumLoader iOS —— 图形界面。

    uv run gui.py

页面在 `webui/`，宿主在这里。设备操作全部复用 `main.py` 那一套
（pymobiledevice3 + house_arrest），没有第二份实现。

线程模型：pywebview 是「主线程跑 GUI、JS 调用落到别的线程」，而 pymobiledevice3 是
asyncio 的。所以这里在后台拉一条常驻事件循环（`LoopRunner`），每次 JS 调用都通过
`run_coroutine_threadsafe` 丢进去；长任务再放到独立线程，页面用 `drain()` 轮询日志与
任务状态 —— 不依赖从工作线程反向 push 到页面，避免 pywebview 的跨线程调用问题。
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymobiledevice3>=11.63",
#   "UnityPy==1.25.3",
#   "pywebview>=5",
# ]
# ///

from __future__ import annotations

import asyncio
import collections
import json
import sys
import threading
import time
from pathlib import Path

import webview

import main as engine

HERE = Path(__file__).resolve().parent
WEBUI = HERE / "webui"
LOADER_ROOT = f"/Documents/{engine.LOADER_DIR}"


def _jsonable(value):
    """pywebview 用 json.dumps 把返回值发给页面；遇到 datetime 之类会整条调用失败。
    这里兜一层，避免将来某个字段又把接口打挂。"""
    return json.loads(json.dumps(value, default=str))


class LoopRunner:
    """常驻 asyncio 事件循环（pymobiledevice3 需要 asyncio，GUI 是线程模型）。"""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._serve, name="cesium-loop", daemon=True).start()

    def _serve(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def call(self, coro, timeout: float = 1800):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)


class Api:
    """页面通过 `window.pywebview.api.*` 调用这里的方法。"""

    def __init__(self) -> None:
        self._loop = LoopRunner()
        self._lines: collections.deque[str] = collections.deque(maxlen=4000)
        self._task: dict = {"name": None, "running": False, "ok": None, "error": None}
        self._report: dict | None = None
        self._mods: list[dict] = []
        self._window = None
        engine.set_output_hook(self._lines.append)

    # ------------------------------------------------------------------ 基础设施

    async def _with_device(self, worker):
        bundle_id, _ = engine.find_game()
        device, session = await engine.open_device(bundle_id)
        try:
            return await worker(device)
        finally:
            await engine.close_device(session)

    def _spawn(self, name: str, coro, after=None) -> dict:
        if self._task.get("running"):
            return {"started": False, "error": f"已有任务在跑：{self._task.get('name')}"}
        self._task = {"name": name, "running": True, "ok": None, "error": None}
        self._lines.append(f"[task] {name} 开始")

        def body() -> None:
            try:
                result = self._loop.call(coro)
                if after is not None:
                    after(result)
                self._task.update(running=False, ok=True)
                self._lines.append(f"[task] {name} 完成")
            except Exception as error:  # noqa: BLE001
                self._task.update(running=False, ok=False, error=str(error))
                self._lines.append(f"[FAIL] {name}: {error}")

        threading.Thread(target=body, name=f"cesium-{name}", daemon=True).start()
        return {"started": True, "name": name}

    # ------------------------------------------------------------------ 轮询/探测

    def drain(self) -> dict:
        """页面每 400ms 调一次：取走累积的输出行与任务状态。"""
        lines = list(self._lines)
        self._lines.clear()
        return {"lines": lines, "task": dict(self._task)}

    def probe(self) -> dict:
        """轻量探测：设备与游戏，不碰容器。"""
        try:
            devices = engine.list_devices()
        except Exception as error:  # noqa: BLE001
            return {"connected": False, "error": str(error)}
        if not devices:
            return {"connected": False, "devices": [],
                    "error": "没有检测到 iOS 设备（USB 连接并信任此电脑）"}
        device = devices[0]
        info = {"name": device.get("DeviceName"), "model": device.get("ProductType"),
                "ios": device.get("ProductVersion"), "usb": device.get("ConnectionType")}
        try:
            bundle_id, app = engine.find_game()
        except Exception as error:  # noqa: BLE001
            return {"connected": True, "device": info, "error": str(error)}
        return {"connected": True, "device": info,
                "game": {"bundle_id": bundle_id, "version": engine.app_version(app),
                         "name": app.get("CFBundleDisplayName") or bundle_id}}

    # ------------------------------------------------------------------ 检测

    async def _snapshot(self) -> dict:
        bundle_id, info = engine.find_game()
        device, session = await engine.open_device(bundle_id)
        try:
            report = await engine.collect(device, engine.app_version(info), engine.load_state())
            mods = await engine.mod_inventory(device, LOADER_ROOT)
            return {"report": report, "mods": mods}
        finally:
            await engine.close_device(session)

    def refresh(self) -> dict:
        def after(result: dict) -> None:
            self._report = result["report"]
            self._mods = result["mods"]

        return self._spawn("检测", self._snapshot(), after=after)

    def get_report(self):
        return _jsonable(self._report) if self._report is not None else None

    def get_mods(self) -> list[dict]:
        return _jsonable(self._mods)

    # ------------------------------------------------------------------ 模组

    def set_mod_enabled(self, mod_id: str, enabled: bool) -> dict:
        async def work():
            moved = await self._with_device(
                lambda d: engine.set_mod_enabled(d, LOADER_ROOT, mod_id, bool(enabled)))
            self._mods = await self._with_device(
                lambda d: engine.mod_inventory(d, LOADER_ROOT))
            return moved

        return self._spawn(f"{'启用' if enabled else '停用'} {mod_id}", work())

    def read_config(self, mod_id: str) -> dict:
        try:
            return self._loop.call(
                self._with_device(lambda d: engine.read_mod_config(d, LOADER_ROOT, mod_id)))
        except Exception as error:  # noqa: BLE001
            return {"id": mod_id, "error": str(error)}

    def write_config(self, mod_id: str, text: str) -> dict:
        try:
            return self._loop.call(
                self._with_device(lambda d: engine.write_mod_config(d, LOADER_ROOT, mod_id, text)))
        except Exception as error:  # noqa: BLE001
            return {"id": mod_id, "error": str(error)}

    # ------------------------------------------------------------------ 日志

    def logs(self) -> list[dict]:
        try:
            return self._loop.call(self._with_device(lambda d: engine.list_logs(d, LOADER_ROOT)))
        except Exception as error:  # noqa: BLE001
            self._lines.append(f"[FAIL] 列日志失败：{error}")
            return []

    def read_log(self, name: str) -> dict:
        try:
            return {"name": name, "text": self._loop.call(
                self._with_device(lambda d: engine.read_log(d, LOADER_ROOT, name)))}
        except Exception as error:  # noqa: BLE001
            return {"name": name, "error": str(error)}

    # ------------------------------------------------------------------ 安装/还原

    def default_payload(self) -> str:
        found = engine.resolve_payload(None)
        return str(found) if found else ""

    def pick_folder(self) -> dict:
        window = self._window or webview.active_window()
        result = window.create_file_dialog(webview.FOLDER_DIALOG, directory=str(HERE))
        if not result:
            return {"path": None}
        path = result[0] if isinstance(result, (list, tuple)) else result
        return {"path": str(path)}

    def install(self, payload: str | None = None, patch: bool = True, deploy: bool = True) -> dict:
        folder = Path(payload).expanduser() if payload else engine.resolve_payload(None)
        if patch is False and deploy is False:
            return {"started": False, "error": "没有勾选任何动作"}
        if deploy and (folder is None or not Path(folder).is_dir()):
            return {"started": False, "error": f"载荷目录不存在：{folder}"}

        async def work():
            return await engine.do_install(Path(folder) if folder else None,
                                           skip_payload=not deploy, skip_patch=not patch)

        return self._spawn("安装", work())

    def restore(self, remove_loader: bool = False) -> dict:
        return self._spawn("完全卸载" if remove_loader else "还原代码包",
                           engine.do_restore(bool(remove_loader)))

    def quit(self) -> None:
        window = self._window or webview.active_window()
        window.destroy()


def main() -> int:
    engine.check_dependencies()

    api = Api()
    window = webview.create_window(
        "CesiumLoader iOS",
        url=str(WEBUI / "index.html"),
        js_api=api,
        width=1200, height=800, min_size=(980, 660),
    )
    api._window = window

    delay = 0.0
    for arg in sys.argv[1:]:
        if arg == "--smoke":
            delay = 8.0
        elif arg.startswith("--smoke="):
            delay = float(arg.split("=", 1)[1])

    if delay > 0:
        def closer() -> None:
            time.sleep(delay)
            try:
                window.destroy()
            except Exception:
                pass
        webview.start(closer, http_server=True)
    else:
        webview.start(http_server=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
