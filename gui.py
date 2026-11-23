#!/usr/bin/env python3
"""AstralParty.Toys.iOS —— 图形界面。

    uv run gui.py

页面由 `webui/`（React + TypeScript + Vite）构建，产物在 `webui/dist/`。
设备操作全部复用 `main.py` 那一套（pymobiledevice3 + house_arrest），没有第二份实现。

线程模型：pywebview 是「主线程跑 GUI、JS 调用落到别的线程」，而 pymobiledevice3 是
asyncio 的。所以这里在后台拉一条常驻事件循环（`LoopRunner`），每次 JS 调用都通过
`run_coroutine_threadsafe` 丢进去；长任务再放到独立线程，页面用 `drain()` 轮询日志与
任务状态 —— 不依赖从工作线程反向 push 到页面。

设备会话是**复用**的（`_ensure_device`）：house_arrest 每次建会话要几百毫秒，
逐次开关会让每次点击都迟钝。同一个 loop 上的多个协程会在 await 处交错，所以用一把
`asyncio.Lock` 把设备操作串起来。
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
import re
import shutil
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import webview

import main as engine

HERE = Path(__file__).resolve().parent
WEBUI = HERE / "webui"
DIST = WEBUI / "dist"
LOADER_ROOT = f"/Documents/{engine.LOADER_DIR}"
APP_VERSION = "0.2.0"
MARKET_BASE = "https://forge.hiynet.com"
CONSENT_VERSION = 2
HTTP_TIMEOUT = 12.0
DOWNLOAD_LIMIT = 512 * 1024 * 1024


def _jsonable(value):
    """pywebview 用 json.dumps 把返回值发给页面；遇到 datetime 之类会整条调用失败。"""
    return json.loads(json.dumps(value, default=str))


def _http_json(url: str, timeout: float = HTTP_TIMEOUT) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": f"AstralParty.Toys.iOS/{APP_VERSION}", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(8 * 1024 * 1024)
    return json.loads(raw.decode("utf-8"))


def _http_download(url: str, target: Path, timeout: float = 60.0) -> int:
    request = urllib.request.Request(
        url, headers={"User-Agent": f"AstralParty.Toys.iOS/{APP_VERSION}"})
    total = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response, open(target, "wb") as sink:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > DOWNLOAD_LIMIT:
                raise RuntimeError("下载超过 512 MB")
            sink.write(chunk)
    return total


def _absolute(base: str, value: str | None) -> str | None:
    """市场返回的 coverUrl / downloadUrl 是相对路径（/api/...），补成绝对地址。

    页面是 http://127.0.0.1:<port>，相对路径会被当成页面自己的地址，封面就全 404 了。
    """
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/"):
        return base + value
    return f"{base}/{value}"


def _locate_mod_root(archive_path: Path, mod_id: str) -> Path:
    """解开市场包并找到真正的模组目录（含 <目录名>.dll 的那一层）。"""
    stage = engine.WORK_DIR / "market" / "extract" / mod_id
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    with zipfile.ZipFile(archive_path) as archive:
        names = engine._zip_members(archive)
        if len(names) > 20000:
            raise RuntimeError("包内条目过多")
        for member in names:
            parts = member.split("/")
            if parts[0] in ("mods", "AstralParty_ModLoader") and len(parts) > 1:
                parts = parts[1:]
            target = stage.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink)

    for candidate in [stage, *[p for p in stage.iterdir() if p.is_dir()]]:
        if (candidate / f"{candidate.name}.dll").is_file():
            return candidate
    for dll in stage.rglob("*.dll"):
        if dll.with_suffix(".json").is_file():
            return dll.parent
    raise RuntimeError("无法识别的包结构（找不到 <ModId>/<ModId>.dll）")



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


class Api:
    """页面通过 `window.pywebview.api.*` 调用这里的方法。

    只暴露方法：pywebview 会把 `js_api` 对象的公开属性也序列化给 JS，
    之前把一个 Window 挂在公开属性上，导致它去递归遍历 WebView2 的 .NET 对象图。
    """

    def __init__(self) -> None:
        self._loop = LoopRunner()
        self._lock = asyncio.Lock()
        self._lines: collections.deque[str] = collections.deque(maxlen=4000)
        self._task: dict = {"name": None, "running": False, "ok": None, "error": None}
        self._report: dict | None = None
        self._mods: list[dict] = []
        self._window = None
        self._device = None
        self._session = None
        engine.set_output_hook(self._lines.append)

    # ------------------------------------------------------------------ 设备会话

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

    # ------------------------------------------------------------------ 基础设施

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
        return _jsonable({"lines": lines, "task": dict(self._task)})

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

    # ------------------------------------------------------------------ 检测

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
        return _jsonable(self._report) if self._report is not None else None

    def get_mods(self) -> list[dict]:
        return _jsonable(self._mods)

    def mods(self) -> list[dict]:
        """只读当前列表（不碰设备），给页面做增量刷新。"""
        return _jsonable(self._mods)

    # ------------------------------------------------------------------ 模组

    def set_mod_enabled(self, mod_id: str, enabled: bool) -> dict:
        async def work(device):
            moved = await engine.set_mod_enabled(device, LOADER_ROOT, mod_id, bool(enabled))
            self._mods = await engine.mod_inventory(device, LOADER_ROOT)
            return moved

        return self._spawn(f"{'启用' if enabled else '停用'} {mod_id}", self._with_device(work))

    def read_config(self, mod_id: str, folder: str | None = None) -> dict:
        try:
            return _jsonable(self._loop.call(self._with_device(
                lambda d: engine.read_mod_config(d, LOADER_ROOT, mod_id, folder))))
        except Exception as error:  # noqa: BLE001
            return {"id": mod_id, "error": str(error)}

    def write_config(self, mod_id: str, text: str, folder: str | None = None) -> dict:
        try:
            return _jsonable(self._loop.call(self._with_device(
                lambda d: engine.write_mod_config(d, LOADER_ROOT, mod_id, text, folder))))
        except Exception as error:  # noqa: BLE001
            return {"id": mod_id, "error": str(error)}

    # ------------------------------------------------------------------ 日志

    def logs(self) -> list[dict]:
        try:
            return _jsonable(self._loop.call(
                self._with_device(lambda d: engine.list_logs(d, LOADER_ROOT))))
        except Exception as error:  # noqa: BLE001
            self._lines.append(f"[FAIL] 列日志失败：{error}")
            return []

    def read_log(self, name: str) -> dict:
        try:
            return {"name": name, "text": self._loop.call(
                self._with_device(lambda d: engine.read_log(d, LOADER_ROOT, name)))}
        except Exception as error:  # noqa: BLE001
            return {"name": name, "error": str(error)}

    def client_error(self, message: str) -> dict:
        """页面报上来的未捕获异常：进输出面板，冒烟时也会打到 stdout。"""
        print(f"[ui] {message}", flush=True)
        self._lines.append(f"[FAIL] 界面错误：{message}")
        return {"ok": True}

    # ------------------------------------------------------------------ 市场

    def _market(self) -> dict:
        state = engine.load_state()
        return dict(state.get("market") or {})

    def _market_write(self, **changes) -> dict:
        state = engine.load_state()
        market = state.setdefault("market", {})
        market.update(changes)
        engine.save_state(state)
        return self.market_state()

    def market_state(self) -> dict:
        market = self._market()
        return {
            "baseUrl": market.get("baseUrl") or MARKET_BASE,
            "consentVersion": int(market.get("consentVersion") or 0),
            "requiredVersion": CONSENT_VERSION,
            "accepted": int(market.get("consentVersion") or 0) >= CONSENT_VERSION,
        }

    def market_consent(self, accepted: bool) -> dict:
        """同意/撤回免责声明。未同意时不会有任何请求打到市场。"""
        return self._market_write(consentVersion=CONSENT_VERSION if accepted else 0)

    def set_market_base(self, url: str) -> dict:
        url = (url or "").strip().rstrip("/")
        if url and not re.match(r"^https?://", url):
            return {"error": "地址必须以 http:// 或 https:// 开头"}
        return {"ok": True, **self._market_write(baseUrl=url or MARKET_BASE)}

    def _require_consent(self) -> None:
        if not self.market_state()["accepted"]:
            raise RuntimeError("未同意免责声明，不会连接市场服务")

    def market_list(self, page: int = 1, lang: str = "zh-Hans") -> dict:
        try:
            self._require_consent()
            base = self.market_state()["baseUrl"].rstrip("/")
            query = urllib.parse.urlencode({"page": int(page), "lang": lang})
            data = _http_json(f"{base}/api/mods?{query}")
            items = data.get("items") or []
            for item in items:
                item["coverUrl"] = _absolute(base, item.get("coverUrl"))
                item["downloadUrl"] = _absolute(base, item.get("downloadUrl"))
            return {"ok": True, "total": data.get("total"), "page": data.get("page"),
                    "pageSize": data.get("pageSize"), "tags": data.get("tags") or [],
                    "items": items}
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "error": str(error)}

    def market_detail(self, mod_id: str, lang: str = "zh-Hans") -> dict:
        try:
            self._require_consent()
            base = self.market_state()["baseUrl"].rstrip("/")
            query = urllib.parse.urlencode({"lang": lang})
            detail = _http_json(f"{base}/api/mods/{urllib.parse.quote(mod_id)}?{query}")
            detail["coverUrl"] = _absolute(base, detail.get("coverUrl"))
            for version in detail.get("versions") or []:
                version["downloadUrl"] = _absolute(base, version.get("downloadUrl"))
            return {"ok": True, "detail": detail}
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "error": str(error)}

    def market_install(self, mod_id: str, version: str | None = None,
                       lang: str = "zh-Hans") -> dict:
        async def work():
            self._require_consent()
            base = self.market_state()["baseUrl"].rstrip("/")
            query = urllib.parse.urlencode({"lang": lang})
            detail = _http_json(f"{base}/api/mods/{urllib.parse.quote(mod_id)}?{query}")
            versions = detail.get("versions") or []
            if not versions:
                raise RuntimeError("该模组没有可下载版本")
            target = next((item for item in versions if item.get("version") == version), None)
            target = target or versions[0]
            url = target.get("downloadUrl") or ""
            if not url:
                raise RuntimeError("这个版本没有下载地址")
            if url.startswith("/"):
                url = base + url

            engine.section("安装市场模组")
            engine.log(f"  {mod_id} {target.get('version') or 'latest'}")
            archive = engine.WORK_DIR / "market" / f"{mod_id}-{target.get('version') or 'latest'}.zip"
            size = _http_download(url, archive)
            actual = engine.sha256_file(archive)
            expect = (target.get("sha256") or "").lower()
            engine.ok(f"已下载 {size} B  {actual[:16]}…")
            if expect and expect != actual:
                raise RuntimeError(f"SHA-256 不匹配：{actual} != {expect}")

            root = _locate_mod_root(archive, mod_id)
            engine.ok(f"包结构识别为 {root.name}")

            await self._release()

            async def push(device):
                mods_dir = f"{LOADER_ROOT}/mods"
                await device.makedirs(mods_dir)
                target_dir = f"{mods_dir}/{root.name}"
                if await device.exists(target_dir):
                    await device.rm(target_dir)
                await device.push(root, mods_dir)
                self._mods = await engine.mod_inventory(device, LOADER_ROOT)
                return {"id": root.name}

            return await self._with_device(push)

        def after(_result) -> None:
            self._report = None

        return self._spawn(f"安装 {mod_id}", work(), after=after)

    # ------------------------------------------------------------------ 文件浏览

    def fs(self, path: str = "/Documents", show_hidden: bool = False) -> dict:
        try:
            entries = self._loop.call(
                self._with_device(lambda d: engine.fs_list(d, path, show_hidden)))
            return _jsonable({"path": path, "entries": entries})
        except Exception as error:  # noqa: BLE001
            return {"path": path, "entries": [], "error": str(error)}

    def fs_file(self, path: str) -> dict:
        try:
            return _jsonable(self._loop.call(
                self._with_device(lambda d: engine.fs_read(d, path))))
        except Exception as error:  # noqa: BLE001
            return {"path": path, "error": str(error)}

    def fs_delete(self, path: str) -> dict:
        if not path.startswith("/Documents/") or path.rstrip("/") == "/Documents":
            return {"error": "只能删除 /Documents 下的内容"}
        try:
            self._loop.call(self._with_device(lambda d: d.rm(path)))
            return {"ok": True}
        except Exception as error:  # noqa: BLE001
            return {"error": str(error)}

    # ------------------------------------------------------------------ 卡面

    def skins(self) -> dict:
        try:
            items = self._loop.call(
                self._with_device(lambda d: engine.skins_list(d, LOADER_ROOT)))
            return {"skins": _jsonable(items)}
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
            return _jsonable(self._loop.call(self._with_device(
                lambda d: engine.skins_activate(d, LOADER_ROOT, name))))
        except Exception as error:  # noqa: BLE001
            return {"error": str(error)}

    # ------------------------------------------------------------------ 设置

    def settings(self) -> dict:
        market = self.market_state()
        return {
            "appVersion": APP_VERSION,
            "payloadDefault": self.default_payload(),
            "market": market,
        }

    # ------------------------------------------------------------------ 安装/还原

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


def main() -> int:
    engine.check_dependencies()

    entry = DIST / "index.html"
    if not entry.exists():
        engine.bad("找不到 webui/dist/index.html —— 先在 webui/ 里执行 pnpm install && pnpm build")
        return 1
    _warn_if_stale_build()

    api = Api()
    window = webview.create_window(
        "AstralParty.Toys.iOS",
        url=str(entry),
        js_api=api,
        width=1200, height=820, min_size=(980, 660),
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

    # 正常退出也把常驻 AFC 会话关掉，别把 reader 任务留在半空
    try:
        api._loop.call(api._release(), timeout=5)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
