"""窗口入口 —— 创建 pywebview 窗口、挂 js_api、跑起来。"""

from __future__ import annotations

import cesium_ios as engine
import sys
import time
import webview

from .api import Api
from .config import APP_VERSION, DIST, WEBUI
from .drop_api import install_drop_target

def _warn_if_stale_build() -> None:
    entry = DIST / "index.html"
    if not entry.exists():
        return
    src = WEBUI / "src"
    if not src.exists():
        return
    newest = max((p.stat().st_mtime for p in src.rglob("*") if p.is_file()), default=0.0)
    if newest > entry.stat().st_mtime:
        engine.warn("前端源码比 dist 新：先在 webui/ 里 pnpm build 再重启界面")


def main() -> int:
    engine.check_dependencies()

    entry = DIST / "index.html"
    if not entry.exists():
        engine.bad("找不到 webui/dist/index.html —— 先在 webui/ 里执行 pnpm install && pnpm build")
        return 1
    _warn_if_stale_build()

    engine.set_log_prefix("gui")  # 本次运行的输出写 logs/gui-<时间戳>.log
    api = Api()
    engine.log(f"AstralParty.Toys.iOS {APP_VERSION} · 界面 {entry}")
    engine.log(f"本次输出日志：{engine.log_path()}")
    window = webview.create_window(
        "AstralParty.Toys.iOS",
        url=str(entry),
        js_api=api,
        width=1200, height=820, min_size=(980, 660),
    )
    api._window = window
    install_drop_target(window, api)

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

    # 正常退出也把常驻 AFC 会话关掉，别把 reader 任务留在半空
    try:
        api._loop.call(api._release(), timeout=5)
    except Exception:
        pass
    return 0
