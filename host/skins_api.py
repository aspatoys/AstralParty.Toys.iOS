"""卡面页宿主方法 —— 方案列表、导入 ZIP、切换启用方案。"""

from __future__ import annotations

from pathlib import Path
import cesium_ios as engine
import webview

from .config import LOADER_ROOT
from .util import jsonable

class SkinsApi:
    """方案列表、导入 ZIP、切换启用方案。"""

    def skins(self) -> dict:
        try:
            items = self._loop.call(
                self._with_device(lambda d: engine.skins_list(d, LOADER_ROOT)))
            return {"skins": jsonable(items)}
        except Exception as error:  # noqa: BLE001
            return {"skins": [], "error": str(error)}


    def pick_zip(self) -> dict:
        window = self._window or webview.active_window()
        result = window.create_file_dialog(
            webview.OPEN_DIALOG, directory=str(Path.home()), allow_multiple=False,
            file_types=("ZIP 包 (*.zip)", "所有文件 (*.*)"))
        if not result:
            return {"path": None}
        return {"path": str(result[0] if isinstance(result, (list, tuple)) else result)}


    def skins_import(self, zip_path: str | None = None, scheme: str | None = None) -> dict:
        target = zip_path or self.pick_zip().get("path")
        if not target:
            return {"started": False, "error": "没有选择 ZIP 包"}

        async def work():
            await self._release()

            async def run(device):
                return await engine.skins_import(device, LOADER_ROOT, target, scheme)

            return await self._with_device(run)

        return self._spawn("导入卡面", work())


    def skins_activate(self, name: str) -> dict:
        try:
            return jsonable(self._loop.call(self._with_device(
                lambda d: engine.skins_activate(d, LOADER_ROOT, name))))
        except Exception as error:  # noqa: BLE001
            return {"error": str(error)}
