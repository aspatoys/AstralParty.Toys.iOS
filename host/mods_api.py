"""模组页宿主方法 —— 检测、模组启停、配置读写、日志。"""

from __future__ import annotations

import cesium_ios as engine

from .config import LOADER_ROOT
from .util import jsonable

class ModsApi:
    """检测、模组启停、配置读写、日志。"""

    async def _snapshot(self) -> dict:
        bundle_id, info = engine.find_game()
        version = engine.app_version(info)

        async def work(device):
            report = await engine.collect(device, version, engine.load_state())
            mods = await engine.mod_inventory(device, LOADER_ROOT)
            return {"report": report, "mods": mods}

        return await self._with_device(work)


    def refresh(self) -> dict:
        def after(result: dict) -> None:
            self._report = result["report"]
            self._mods = result["mods"]

        return self._spawn("检测", self._snapshot(), after=after)


    def get_report(self):
        return jsonable(self._report) if self._report is not None else None


    def get_mods(self) -> list[dict]:
        return jsonable(self._mods)


    def mods(self) -> list[dict]:
        """只读当前列表（不碰设备），给页面做增量刷新。"""
        return jsonable(self._mods)


    def set_mod_enabled(self, mod_id: str, enabled: bool) -> dict:
        async def work(device):
            moved = await engine.set_mod_enabled(device, LOADER_ROOT, mod_id, bool(enabled))
            self._mods = await engine.mod_inventory(device, LOADER_ROOT)
            return moved

        return self._spawn(f"{'启用' if enabled else '停用'} {mod_id}", self._with_device(work))


    def read_config(self, mod_id: str, folder: str | None = None) -> dict:
        try:
            return jsonable(self._loop.call(self._with_device(
                lambda d: engine.read_mod_config(d, LOADER_ROOT, mod_id, folder))))
        except Exception as error:  # noqa: BLE001
            return {"id": mod_id, "error": str(error)}


    def write_config(self, mod_id: str, text: str, folder: str | None = None) -> dict:
        try:
            return jsonable(self._loop.call(self._with_device(
                lambda d: engine.write_mod_config(d, LOADER_ROOT, mod_id, text, folder))))
        except Exception as error:  # noqa: BLE001
            return {"id": mod_id, "error": str(error)}


    def logs(self) -> list[dict]:
        try:
            return jsonable(self._loop.call(
                self._with_device(lambda d: engine.list_logs(d, LOADER_ROOT))))
        except Exception as error:  # noqa: BLE001
            engine.log(f"[FAIL] 列日志失败：{error}")
            return []


    def read_log(self, name: str) -> dict:
        try:
            return {"name": name, "text": self._loop.call(
                self._with_device(lambda d: engine.read_log(d, LOADER_ROOT, name)))}
        except Exception as error:  # noqa: BLE001
            return {"name": name, "error": str(error)}
