"""系统拖放 —— 把拖进窗口的本地路径交给页面，并注册 WebView2 的 drop 监听。"""

from __future__ import annotations

from pathlib import Path
import cesium_ios as engine
import threading
import time
from typing import TYPE_CHECKING

from .util import jsonable

if TYPE_CHECKING:  # 只为类型标注，运行时不引入（api.py 会导入本模块）
    from .api import Api


def install_drop_target(window, api: "Api") -> None:
    """让窗口能接收从系统拖进来的文件（WebView2 才能给出完整本地路径）。

    必须走 pywebview 的 DOM API 注册 drop 监听：只有它会把 WebView2 的
    `CoreWebView2File` 对象带出来，页面自己的 HTML5 drop 事件拿不到路径。
    """

    def register() -> None:
        try:
            from webview.dom import DOMEventHandler

            window.dom.body.on("drop", DOMEventHandler(api._on_files_dropped, prevent_default=True))
            window.dom.body.on("dragover", DOMEventHandler(lambda _event: None, prevent_default=True))
        except Exception as error:  # noqa: BLE001
            engine.warn(f"没能注册窗口拖放接收器（系统拖入不可用）：{error}")

    def on_loaded() -> None:
        threading.Thread(target=register, name="cesium-drop", daemon=True).start()

    window.events.loaded += on_loaded


class DropApi:
    """把拖进窗口的本地路径交给页面，并注册 WebView2 的 drop 监听。"""

    def _on_files_dropped(self, event) -> None:
        """pywebview 的 DOM drop 处理器：收集拖进窗口的本地路径等页面来取。

        路径由 pywebview 从 WebView2 的 CoreWebView2File 里带出来，页面侧看不到完整
        路径，所以只能从这里转一手。目标目录由页面决定。
        """
        try:
            files = ((event or {}).get("dataTransfer") or {}).get("files") or []
        except Exception:  # noqa: BLE001
            files = []
        paths = [str(item.get("pywebviewFullPath")) for item in files
                 if isinstance(item, dict) and item.get("pywebviewFullPath")]
        if not paths:
            return
        self._drops.append({"paths": paths, "names": [Path(p).name for p in paths],
                            "at": time.time()})
        engine.log(f"[drop] 收到 {len(paths)} 个本地项目，等待界面确认目标目录")


    def fs_drops(self) -> list[dict]:
        """页面轮询：取走拖进窗口的文件批次（取走即清空）。"""
        batches = list(self._drops)
        self._drops.clear()
        return jsonable(batches)
