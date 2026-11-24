"""设备会话与任务槽 —— 会话复用、任务串行、drain 轮询、设备探测。"""

from __future__ import annotations

import cesium_ios as engine
import threading

from .util import jsonable

class SessionApi:
    """会话复用、任务串行、drain 轮询、设备探测。"""

    async def _ensure_device(self):
        if self._device is not None:
            return self._device
        bundle_id, _ = engine.find_game()
        device, session = await engine.open_device(bundle_id)
        self._device, self._session = device, session
        return device


    async def _drop_device(self) -> None:
        session, self._session, self._device = self._session, None, None
        if session is not None:
            try:
                await engine.close_device(session)
            except Exception:
                pass


    async def _with_device(self, worker):
        async with self._lock:
            device = await self._ensure_device()
            try:
                return await worker(device)
            except Exception:
                # 会话可能已经失效（设备重连等），丢掉让下一次调用重来
                await self._drop_device()
                raise


    async def _release(self) -> None:
        async with self._lock:
            await self._drop_device()


    def disconnect(self) -> dict:
        """设备重新插拔后，页面可以用它强制重连。"""
        self._loop.call(self._release())
        return {"ok": True}


    def _spawn(self, name: str, coro, after=None) -> dict:
        if self._task.get("running"):
            return {"started": False, "error": f"已有任务在跑：{self._task.get('name')}"}
        self._task = {"name": name, "running": True, "ok": None, "error": None}
        engine.log(f"[task] {name} 开始")

        def body() -> None:
            try:
                result = self._loop.call(coro)
                if after is not None:
                    after(result)
                self._task.update(running=False, ok=True)
                engine.log(f"[task] {name} 完成")
            except Exception as error:  # noqa: BLE001
                self._task.update(running=False, ok=False, error=str(error))
                engine.log(f"[FAIL] {name}: {error}")

        threading.Thread(target=body, name=f"cesium-{name}", daemon=True).start()
        return {"started": True, "name": name}


    def drain(self) -> dict:
        """页面每 400ms 调一次：取走累积的输出行与任务状态。"""
        lines = list(self._lines)
        self._lines.clear()
        return jsonable({"lines": lines, "task": dict(self._task)})


    def probe(self) -> dict:
        """轻量探测：设备与游戏，不碰容器（也不建容器会话）。"""
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


    def client_error(self, message: str) -> dict:
        """页面报上来的未捕获异常：进输出面板与日志文件，冒烟时也会打到 stdout。"""
        print(f"[ui] {message}", flush=True)
        engine.log(f"[FAIL] 界面错误：{message}")
        return {"ok": True}
