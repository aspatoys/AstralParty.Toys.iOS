"""文件页宿主方法 —— 浏览、增删改移、上传下载、双击打开。"""

from __future__ import annotations

from pathlib import Path
import cesium_ios as engine
import webview

from .util import jsonable

class FilesApi:
    """浏览、增删改移、上传下载、双击打开。"""

    def fs(self, path: str = "/Documents", show_hidden: bool = False) -> dict:
        try:
            entries = self._loop.call(
                self._with_device(lambda d: engine.fs_list(d, path, show_hidden)))
            return jsonable({"path": path, "entries": entries})
        except Exception as error:  # noqa: BLE001
            return {"path": path, "entries": [], "error": str(error)}


    def fs_file(self, path: str) -> dict:
        try:
            return jsonable(self._loop.call(
                self._with_device(lambda d: engine.fs_read(d, path))))
        except Exception as error:  # noqa: BLE001
            return {"path": path, "error": str(error)}


    def fs_open(self, path: str) -> dict:
        """双击：拉到临时目录后用系统默认程序打开。"""
        try:
            return jsonable(self._loop.call(
                self._with_device(lambda d: engine.fs_download_open(d, path))))
        except Exception as error:  # noqa: BLE001
            return {"path": path, "error": str(error)}


    def _fs_after(self, label: str):
        """把引擎侧的结果写成输出行；全军覆没时让任务真的失败。"""

        def after(result) -> None:
            if not isinstance(result, dict):
                return
            done = 0
            for key in ("copied", "moved", "uploaded", "saved", "deleted"):
                items = result.get(key) or []
                done += len(items)
                for item in items[:6]:
                    engine.ok(str(item))
                if len(items) > 6:
                    engine.ok(f"… 其余 {len(items) - 6} 项")
            skipped = result.get("skipped") or []
            for item in skipped[:6]:
                engine.warn(f"跳过 {item}")
            failures = result.get("failed") or []
            for item in failures[:8]:
                engine.warn(f"{item.get('path')}：{item.get('error')}")
            if failures and not done:
                raise RuntimeError(f"{label}失败：{failures[0].get('error')}")
            engine.ok(f"{label}完成，共 {done} 项"
                      + (f"，{len(skipped)} 项跳过" if skipped else "")
                      + (f"，{len(failures)} 项失败" if failures else ""))

        return after


    def _paths(value) -> list[str]:
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if str(item).strip()]
        if value is None or str(value).strip() == "":
            return []
        return [str(value)]


    def fs_mkdir(self, base: str, name: str) -> dict:
        label = f"新建文件夹 {name}"
        return self._spawn(label, self._with_device(
            lambda d: engine.fs_mkdir(d, base, name)), after=self._fs_after("新建文件夹"))


    def fs_rename(self, path: str, name: str) -> dict:
        return self._spawn(f"重命名为 {name}", self._with_device(
            lambda d: engine.fs_rename(d, path, name)), after=self._fs_after("重命名"))


    def fs_delete(self, paths) -> dict:
        items = self._paths(paths)
        if not items:
            return {"started": False, "error": "没有选中任何项目"}
        return self._spawn(f"删除 {len(items)} 项", self._with_device(
            lambda d: engine.fs_delete(d, items)), after=self._fs_after("删除"))


    def fs_transfer(self, sources, target: str, mode: str = "copy",
                    conflict: str = "rename") -> dict:
        """复制/剪切：mode = copy | move。"""
        items = self._paths(sources)
        if not items:
            return {"started": False, "error": "没有选中任何项目"}
        moving = str(mode).lower() == "move"
        label = "移动" if moving else "复制"
        worker = engine.fs_move if moving else engine.fs_copy
        return self._spawn(
            f"{label} {len(items)} 项",
            self._with_device(lambda d: worker(d, items, target, conflict)),
            after=self._fs_after(label))


    def fs_pick_dir(self, title: str = "选择保存位置") -> dict:
        window = self._window or webview.active_window()
        result = window.create_file_dialog(
            webview.FOLDER_DIALOG, directory=str(Path.home()), allow_multiple=False)
        if not result:
            return {"path": None}
        return {"path": str(result[0] if isinstance(result, (list, tuple)) else result)}


    def fs_pick_files(self) -> dict:
        window = self._window or webview.active_window()
        result = window.create_file_dialog(
            webview.OPEN_DIALOG, directory=str(Path.home()), allow_multiple=True)
        if not result:
            return {"paths": []}
        if isinstance(result, (list, tuple)):
            return {"paths": [str(item) for item in result]}
        return {"paths": [str(result)]}


    def fs_download(self, sources, local_dir: str | None = None) -> dict:
        items = self._paths(sources)
        if not items:
            return {"started": False, "error": "没有选中任何项目"}
        dest = local_dir or self.fs_pick_dir().get("path")
        if not dest:
            return {"started": False, "error": "没有选择保存目录"}
        return self._spawn(f"下载 {len(items)} 项", self._with_device(
            lambda d: engine.fs_download(d, items, dest)), after=self._fs_after("下载"))


    def fs_upload(self, target: str, local_paths=None, conflict: str = "overwrite") -> dict:
        items = self._paths(local_paths)
        if not items:
            items = self.fs_pick_files().get("paths") or []
        if not items:
            return {"started": False, "error": "没有选择要上传的文件"}
        return self._spawn(f"上传 {len(items)} 项", self._with_device(
            lambda d: engine.fs_upload(d, items, target, conflict)),
            after=self._fs_after("上传"))
