"""拉取官方发行包 —— 从 GitHub Release 取加载器载荷（SDK + 模组 + 安卓引导）。

iOS 的载荷由两处官方产物拼成：

- **CesiumLoader 发行包**（`higashitaniyume/CesiumLoader` 的 `cesium-loader.zip`）里是
  `AstralParty_ModLoader/sdk/CesiumLoader.SDK.dll` 与 `AstralParty_ModLoader/mods/**`；
- **安卓引导**（`CesiumLoader.Android.Bootstrap.dll`，可选还有 `CesiumAndroidApi.dll`）不在
  发行包里，它跟着安卓 App 走，得从安卓发行包的 APK 资产 `assets/cesium/` 里取。

两个包都按各自 `version.json` 里的 SHA-256 校验；下载落在 `work/release/`，命中就不重复下。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from .output import log, warn
from .paths import LOADER_DIR, ROOT, WORK_DIR
from .payload import SDK_RELATIVE, sdk_bytes_ios_capable

LOADER_REPO = "higashitaniyume/CesiumLoader"
ANDROID_REPO = "higashitaniyume/AstralParty.Toys.Android"
GITHUB = "https://github.com"
GITHUB_API = "https://api.github.com/repos"
USER_AGENT = "AstralParty.Toys.iOS"

# 发行包里这些东西对运行时没用（和 deploy 的跳过口径一致）
SKIP_SUFFIXES = {".pdb", ".xml", ".txt", ".md"}
# 模组自己的玩家配置：不覆盖也不写入（设备上的那份才是玩家的）
SKIP_NAMES = {"config.json", "mod.cfg"}
# 发行包里的托管部分都在这个前缀下，其中只有下面这两类要上设备
MANAGED_PREFIX = "AstralParty_ModLoader/"

BOOTSTRAP_DLL = "CesiumLoader.Android.Bootstrap.dll"
ANDROID_API_DLL = "CesiumAndroidApi.dll"
APK_BOOTSTRAP = "assets/cesium/bootstrap/" + BOOTSTRAP_DLL
APK_API = "assets/cesium/" + ANDROID_API_DLL

DOWNLOAD_LIMIT = 256 * 1024 * 1024


def payload_dir() -> Path:
    return ROOT / "payload" / LOADER_DIR


def _mirror() -> str:
    """GitHub 访问不畅时的前缀镜像（`https://mirror.example/https://github.com/...`）。"""
    value = os.environ.get("CESIUM_GH_MIRROR", "").strip()
    return value.rstrip("/") + "/" if value else ""


def _open(url: str, timeout: float = 60.0):
    target = _mirror() + url if _mirror() else url
    request = urllib.request.Request(target, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)


def latest_manifest(repo: str) -> dict:
    """读 `releases/latest/download/version.json`（比走 API 少一次限流）。"""
    url = f"{GITHUB}/{repo}/releases/latest/download/version.json"
    with _open(url) as response:
        raw = response.read(4 * 1024 * 1024)
    return json.loads(raw.decode("utf-8"))


def _package(manifest: dict, key: str) -> dict:
    entry = ((manifest.get("packages") or {}).get(key) or {})
    if not entry.get("url"):
        raise RuntimeError(f"发行清单里没有 {key} 的下载地址")
    return entry


def download(entry: dict, progress=None, label: str = "") -> Path:
    """按清单里的 URL / SHA-256 下载到 work/release/，已下过且校验通过就复用。"""
    folder = WORK_DIR / "release"
    folder.mkdir(parents=True, exist_ok=True)
    name = entry.get("fileName") or Path(urllib.parse.urlparse(entry["url"]).path).name
    target = folder / name
    expect = (entry.get("sha256") or "").lower()
    size = int(entry.get("size") or 0)

    if target.exists() and (not expect or _sha256(target) == expect):
        if progress:
            progress(f"  已缓存 {name}")
        return target

    if progress:
        progress(f"  下载 {label or name}"
                 + (f"（{size / 1048576:.1f} MB）" if size else ""))
    digest = hashlib.sha256()
    total = 0
    milestone = 0.0
    with _open(entry["url"]) as response, open(target, "wb") as sink:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > DOWNLOAD_LIMIT:
                sink.close()
                target.unlink(missing_ok=True)
                raise RuntimeError("下载超过 256 MB")
            digest.update(chunk)
            sink.write(chunk)
            if progress and size and total / size >= milestone + 0.25:
                milestone = int(total / size * 4) / 4
                progress(f"  {name} {total / 1048576:.1f}/{size / 1048576:.1f} MB")
    actual = digest.hexdigest()
    if expect and actual != expect:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"{name} 的 SHA-256 不匹配：{actual} != {expect}")
    if progress:
        progress(f"  下载完成 {name}（{total / 1048576:.1f} MB）")
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wanted(relative: str) -> bool:
    """发行包里哪些条目要落进载荷。

    只取托管部分：`sdk/CesiumLoader.SDK.dll` 与 `mods/**` —— 这和安卓端导入发行包的
    口径一致；`bootstrap/CesiumLoader.Bootstrap.dll` 是**桌面**引导，`doorstop_config.json`
    与根目录的 `version.dll` 也只有桌面用得上。
    """
    if relative == SDK_RELATIVE:
        return True
    if not relative.startswith("mods/"):
        return False
    if Path(relative).suffix.lower() in SKIP_SUFFIXES:
        return False
    return Path(relative).name.lower() not in SKIP_NAMES


def extract_loader(zip_path: Path, target_root: Path, progress=None) -> dict:
    """把发行包里的 sdk/ 与 mods/ 合并进载荷目录（不删已有文件）。

    SDK 会额外挑一下：发行包可能还是只会走 Win32 的旧构建，装到 iOS 上会让
    热键模组每帧抛 user32.dll 异常、把游戏卡死，所以这种 SDK 不写进载荷（保留原有的）。
    """
    written: list[str] = []
    skipped = 0
    mods: set[str] = set()
    sdk_status = "absent"
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        if len(names) > 20000:
            raise RuntimeError("发行包条目过多")
        for name in sorted(names):
            if not name.startswith(MANAGED_PREFIX):
                continue  # 桌面用得到的 version.dll / CesiumLoader.dll 之类不上设备
            relative = name[len(MANAGED_PREFIX):]
            if relative == "doorstop_config.json" or not _wanted(relative):
                skipped += 1
                continue
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative == SDK_RELATIVE:
                data = archive.read(name)
                if not sdk_bytes_ios_capable(data):
                    sdk_status = "native-only"
                    skipped += 1
                    continue
                target.write_bytes(data)
                sdk_status = "written"
            else:
                with archive.open(name) as source, open(target, "wb") as sink:
                    shutil.copyfileobj(source, sink)
            written.append(relative)
            parts = relative.split("/")
            if len(parts) >= 2 and parts[0] == "mods":
                mods.add(parts[1])
    if progress:
        progress(f"  写入 {len(written)} 个文件、{len(mods)} 个模组（跳过 {skipped} 个非运行时文件）")
        if sdk_status == "native-only":
            progress("  发行包里的 SDK 没有「退回 Unity 后端」的兜底，没有写进载荷")
    return {"files": written, "mods": sorted(mods), "skipped": skipped, "sdk": sdk_status}


def ensure_android_assets(target_root: Path, force: bool = False, progress=None) -> dict:
    """从安卓发行包的 APK 里取引导 DLL / 悬浮窗 API（载荷里已经有就不动）。"""
    result = {"bootstrap": "kept", "android_api": "kept", "apk": None}
    need_bootstrap = force or not (target_root / BOOTSTRAP_DLL).is_file()
    need_api = not (target_root / ANDROID_API_DLL).is_file()
    if not need_bootstrap and not need_api:
        if progress:
            progress("  引导 DLL 与悬浮窗 API 已存在，跳过安卓包")
        return result

    manifest = latest_manifest(ANDROID_REPO)
    apk = download(_package(manifest, "androidApk"), progress, label="安卓 App（只为取引导 DLL）")
    version = manifest.get("version") or manifest.get("releaseTag") or "?"
    result["apk"] = f"{apk.name}（App {version}）"
    with zipfile.ZipFile(apk) as archive:
        if need_bootstrap:
            _extract_entry(archive, APK_BOOTSTRAP, target_root / BOOTSTRAP_DLL)
            result["bootstrap"] = "updated"
        if need_api and APK_API in archive.namelist():
            _extract_entry(archive, APK_API, target_root / ANDROID_API_DLL)
            result["android_api"] = "updated"
    if progress:
        progress(f"  引导 DLL {result['bootstrap']}，悬浮窗 API {result['android_api']}（来自 {apk.name}）")
    return result


def _extract_entry(archive: zipfile.ZipFile, name: str, target: Path) -> None:
    if name not in archive.namelist():
        raise RuntimeError(f"安卓包里没有 {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(name) as source, open(target, "wb") as sink:
        shutil.copyfileobj(source, sink)


def pull_latest(target_root: Path | None = None, with_android: bool = True,
                force_android: bool = False, progress=None) -> dict:
    """拉最新加载器：SDK + 模组来自发行包，引导 DLL 来自安卓包。"""
    report_cb = progress or (lambda _message: None)
    root = Path(target_root) if target_root else payload_dir()
    root.mkdir(parents=True, exist_ok=True)

    report_cb("读取 CesiumLoader 发行清单…")
    manifest = latest_manifest(LOADER_REPO)
    version = manifest.get("version") or manifest.get("releaseTag") or "?"
    report_cb(f"最新版本：{version}（{manifest.get('releaseTag') or ''}）")
    archive = download(_package(manifest, "loaderZip"), progress, label="加载器发行包")

    summary = extract_loader(archive, root, progress)
    summary["version"] = str(version)
    summary["releaseTag"] = manifest.get("releaseTag")
    summary["payload"] = str(root)
    summary["android"] = (ensure_android_assets(root, force=force_android, progress=progress)
                          if with_android else {"bootstrap": "skipped", "android_api": "skipped", "apk": None})

    missing = [name for name in (BOOTSTRAP_DLL,) if not (root / name).is_file()]
    if not (root / SDK_RELATIVE).is_file():
        missing.append(f"{SDK_RELATIVE}（要在没有 user32 的平台上也能跑的构建）")
    summary["missing"] = missing
    if summary.get("sdk") == "native-only" and (root / SDK_RELATIVE).is_file():
        warn("发行包里的 SDK 只走 Win32 后端，已保留载荷里原有的 SDK；"
             "要更新 SDK 请等加载器发布带 Unity 兜底的版本")
    if missing:
        warn(f"载荷里还缺 {', '.join(missing)} —— 补齐后再点「一键安装」")
    return summary
