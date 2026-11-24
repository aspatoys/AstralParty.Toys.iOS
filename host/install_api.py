"""安装页宿主方法 —— 载荷选择、安装/还原/卸载、设置项。"""

from __future__ import annotations

from pathlib import Path
import asyncio

import cesium_ios as engine
import webview

from .config import APP_VERSION, HERE

class InstallApi:
    """载荷选择、安装/还原/卸载、设置项。"""

    def settings(self) -> dict:
        market = self.market_state()
        return {
            "appVersion": APP_VERSION,
            "payloadDefault": self.default_payload(),
            "market": market,
            # 输出面板里的每一行也会落到这里（本机 logs/，一次运行一个文件）
            "logFile": str(engine.log_path()) if engine.log_path() else "",
            "logDir": str(engine.log_dir()),
        }


    def open_logs(self) -> dict:
        """用系统文件管理器打开本机日志目录。"""
        folder = engine.log_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            engine.open_with_default(folder)
            return {"ok": True, "path": str(folder)}
        except Exception as error:  # noqa: BLE001
            return {"path": str(folder), "error": str(error)}


    def pull_loader(self, with_android: bool = True, force_android: bool = False,
                    target: str | None = None) -> dict:
        """拉取最新 CesiumLoader 载荷（下载是阻塞的，丢到线程里做，别占事件循环）。"""

        async def work():
            folder = Path(target).expanduser() if target else None
            return await asyncio.to_thread(
                engine.pull_latest, folder, bool(with_android), bool(force_android), engine.log)

        def after(result) -> None:
            if not isinstance(result, dict):
                return
            engine.ok(f"载荷已更新到 {result.get('version')}："
                      f"{len(result.get('mods') or [])} 个模组 -> {result.get('payload')}")
            if result.get("missing"):
                engine.warn("载荷还缺：" + ", ".join(result["missing"]))

        return self._spawn("拉取最新 CesiumLoader", work(), after=after)


    def default_payload(self) -> str:
        found = engine.resolve_payload(None)
        return str(found) if found else ""


    def pick_folder(self) -> dict:
        window = self._window or webview.active_window()
        result = window.create_file_dialog(webview.FOLDER_DIALOG, directory=str(HERE))
        if not result:
            return {"path": None}
        return {"path": str(result[0] if isinstance(result, (list, tuple)) else result)}


    def install(self, payload: str | None = None, patch: bool = True, deploy: bool = True) -> dict:
        folder = Path(payload).expanduser() if payload else engine.resolve_payload(None)
        if not patch and not deploy:
            return {"started": False, "error": "没有勾选任何动作"}
        if deploy and (folder is None or not Path(folder).is_dir()):
            return {"started": False, "error": f"载荷目录不存在：{folder}"}

        async def work():
            # 长任务会自己重建会话，先释放常驻会话避免占着 AFC
            await self._release()
            return await engine.do_install(Path(folder) if folder else None,
                                           skip_payload=not deploy, skip_patch=not patch)

        def after(_result) -> None:
            self._report = None  # 状态变了，强制页面重新检测

        return self._spawn("安装", work(), after=after)


    def restore(self, remove_loader: bool = False) -> dict:
        async def work():
            await self._release()
            return await engine.do_restore(bool(remove_loader))

        def after(_result) -> None:
            self._report = None

        return self._spawn("完全卸载" if remove_loader else "还原代码包", work(), after=after)


    def quit(self) -> None:
        try:
            self._loop.call(self._release(), timeout=10)
        except Exception:
            pass
        window = self._window or webview.active_window()
        window.destroy()
