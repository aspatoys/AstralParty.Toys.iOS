#!/usr/bin/env python3
"""CesiumLoader iOS 安装 / 检测工具。

免越狱实现：游戏的热更代码包（承载 `AstralParty.Runtime.dll` 的 Addressables bundle）
是**运行时下载进 app 自身容器**的数据文件，不在签名过的 `.app` 里，因此可以直接改写。
容器读写走 `com.apple.mobile.house_arrest`（`VendDocuments`），无需越狱、无需解密
IPA、无需重签名。

    python cesium_ios.py                     # 交互式菜单
    python cesium_ios.py detect [--json]
    python cesium_ios.py install --payload <目录>
    python cesium_ios.py restore
    python cesium_ios.py uninstall

依赖由 PEP 723 内联声明，用 uv 直接跑即可（无需手动建环境）：

    uv run tools/cesium_ios.py

还需要 .NET 8 SDK —— 首次运行会自动编译 tools/CesiumIosPatcher 注入器。
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymobiledevice3>=11.63",
#   "UnityPy==1.25.3",
# ]
# ///

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent   # 本文件所在目录（iOS/）
ROOT = HERE                             # 数据目录与本脚本同级
TOOLS = HERE / "tools"
STATE_PATH = ROOT / "state.json"
BACKUP_DIR = ROOT / "backups"
WORK_DIR = ROOT / "work"

ASSET_NAME = "AstralParty.Runtime.dll"
ADDR_REL = "com.unity.addressables"
BUNDLES_REL = ADDR_REL + "/AssetBundles"
LOADER_DIR = "CesiumLoader"
BOOT_DLL = "CesiumLoader.Android.Bootstrap.dll"
BOOT_TYPE = "CesiumLoader.Android.Bootstrap.Boot"
BOOT_METHOD = "LoadForGame"
PATCH_MARKER = BOOT_TYPE.encode()             # #Strings 堆里可能出现 ASCII 形式
PATCH_MARKER_UTF16 = BOOT_TYPE.encode("utf-16-le")  # ldstr 字面量在 #US 堆里是 UTF-16

# 见过/可能的包名（国服 iOS 是 com.feimo.astralpartycn，与安卓不同）
CANDIDATE_IDS = (
    "com.feimo.astralpartycn",
    "com.feimo.astralparty",
    "com.feimo.jxpd",
    "com.feimo.astralparty.cesium",
)


# --------------------------------------------------------------------------- 输出

_OUTPUT_HOOK = None


def set_output_hook(hook) -> None:
    """把输出接给 GUI（传 None 恢复打印到 stdout）。"""
    global _OUTPUT_HOOK
    _OUTPUT_HOOK = hook


def log(message: str = "") -> None:
    if _OUTPUT_HOOK is not None:
        try:
            _OUTPUT_HOOK(str(message))
            return
        except Exception:
            pass
    print(message, flush=True)


def ok(message: str) -> None:
    log(f"  [ok]   {message}")


def warn(message: str) -> None:
    log(f"  [warn] {message}")


def bad(message: str) -> None:
    log(f"  [FAIL] {message}")


def section(title: str) -> None:
    log(f"\n=== {title} ===")


# --------------------------------------------------------------------------- 状态

def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- catalog

def _i32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def _read_object(data: bytes, offset: int):
    kind = data[offset]
    offset += 1
    if kind == 0:
        return data[offset + 4:offset + 4 + _i32(data, offset)].decode("ascii", "ignore")
    if kind == 1:
        length = _i32(data, offset)
        return data[offset + 4:offset + 4 + length * 2].decode("utf-16-le", "ignore")
    if kind == 2:
        return struct.unpack_from("<H", data, offset)[0]
    if kind == 3:
        return struct.unpack_from("<I", data, offset)[0]
    if kind == 4:
        return _i32(data, offset)
    if kind == 5:
        return "Hash128:" + data[offset:offset + 16].hex()
    return None


class Catalog:
    """Addressables catalog 的 `m_*DataString` 解码（只取定位 bundle 所需的部分）。"""

    def __init__(self, path: Path):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.build_result_hash = raw.get("m_BuildResultHash", "")
        self.internal_ids = raw["m_InternalIds"]
        key_data = base64.b64decode(raw["m_KeyDataString"])
        bucket_data = base64.b64decode(raw["m_BucketDataString"])
        entry_data = base64.b64decode(raw["m_EntryDataString"])

        count = _i32(bucket_data, 0)
        cursor = 4
        self.buckets = []
        for _ in range(count):
            offset = _i32(bucket_data, cursor); cursor += 4
            entries = _i32(bucket_data, cursor); cursor += 4
            self.buckets.append(
                (offset, [_i32(bucket_data, cursor + 4 * i) for i in range(entries)]))
            cursor += 4 * entries
        self.keys = [_read_object(key_data, self.buckets[i][0]) for i in range(count)]

        count = _i32(entry_data, 0)
        cursor = 4
        self.entries = []
        for _ in range(count):
            self.entries.append(struct.unpack_from("<7i", entry_data, cursor))
            cursor += 28

    def bundle_hash_for(self, asset_key: str) -> str | None:
        """返回承载该资产键的 bundle 文件哈希（即远端文件名去掉 `.bundle`）。"""
        for index, key in enumerate(self.keys):
            if key != asset_key:
                continue
            for entry_index in self.buckets[index][1]:
                dependency = self.entries[entry_index][2]
                if 0 <= dependency < len(self.keys):
                    name = self.keys[dependency]
                    if isinstance(name, str) and name.endswith(".bundle"):
                        return name[: -len(".bundle")]
        return None


# --------------------------------------------------------------------------- 设备通道

def _house_arrest():
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService
    return create_using_usbmux, HouseArrestService


class Device:
    """`Documents` 子树内的读写（`VendContainer` 对 App Store 应用会被拒）。"""

    def __init__(self, bundle_id: str, service):
        self.bundle_id = bundle_id
        self.svc = service

    async def ls(self, remote: str) -> list[str]:
        return sorted(await self.svc.listdir(remote))

    async def exists(self, remote: str) -> bool:
        return await self.svc.exists(remote)

    async def read(self, remote: str) -> bytes:
        return await self.svc.get_file_contents(remote)

    async def write(self, remote: str, data: bytes) -> None:
        await self.svc.set_file_contents(remote, data)

    async def rm(self, remote: str) -> None:
        await self.svc.rm(remote)

    async def rename(self, src: str, dst: str) -> None:
        await self.svc.rename(src, dst)

    async def stat(self, remote: str) -> dict:
        return await self.svc.stat(remote)

    async def pull(self, remote: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        await self.svc.pull(remote, str(local))

    async def push(self, local: Path, remote_dir: str) -> None:
        await self.svc.push(str(local), remote_dir)

    async def makedirs(self, remote: str) -> None:
        # AfcService.makedirs 只有 filename 一个参数，重复创建会报错，所以先判存在
        if await self.svc.exists(remote):
            return
        await self.svc.makedirs(remote)


class _Session:
    def __init__(self, lockdown, service):
        self.lockdown = lockdown
        self.service = service


async def open_device(bundle_id: str) -> tuple[Device, _Session]:
    create_using_usbmux, HouseArrestService = _house_arrest()
    lockdown = await create_using_usbmux(autopair=True)
    try:
        service = await HouseArrestService.create(lockdown, bundle_id, documents_only=True)
    except Exception:
        await lockdown.close()
        raise
    return Device(bundle_id, service), _Session(lockdown, service)


async def close_device(session: _Session) -> None:
    try:
        await session.service.close()
    finally:
        await session.lockdown.close()


# --------------------------------------------------------------------------- 设备/应用发现

def check_dependencies() -> None:
    """早失败：缺依赖时直接说清楚是哪个解释器缺什么，别一路走到「没找到游戏」。"""
    missing = []
    for module in ("pymobiledevice3", "UnityPy"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        raise RuntimeError(
            "缺少 Python 依赖：" + "、".join(missing) + "\n"
            f"  当前解释器：{sys.executable}\n"
            "  解决：pip install -r requirements.txt\n"
            "  （要确保跑这个脚本的 python 就是装依赖的那个）")


def run_pmd(*args: str) -> tuple[int, str, str]:
    """调用 pymobiledevice3 CLI（只用于设备与应用列表这类一次性查询）。"""
    result = subprocess.run([sys.executable, "-m", "pymobiledevice3", *args],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout or "", result.stderr or ""


def list_devices() -> list[dict]:
    code, out, err = run_pmd("usbmux", "list")
    if code != 0:
        if "No module named" in err:
            check_dependencies()  # 会抛出说明缺哪个包
        detail = err.strip().splitlines()[-1][:300] if err.strip() else f"退出码 {code}"
        raise RuntimeError("枚举设备失败：" + detail)
    match = re.search(r"\[.*\]", out, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except Exception:
        return []


def app_info(bundle_id: str) -> dict | None:
    code, text, err = run_pmd("apps", "query", bundle_id)
    if code != 0 and "No module named" in err:
        check_dependencies()
    start = text.find("{")
    if start < 0:
        return None
    try:
        data = json.loads(text[start:])
    except Exception:
        return None
    # `apps query` 返回的是 {bundle_id: {...}} 形式
    if isinstance(data, dict) and bundle_id in data and isinstance(data[bundle_id], dict):
        return data[bundle_id]
    return data if isinstance(data, dict) and data.get("CFBundleIdentifier") else None


def find_game() -> tuple[str, dict]:
    devices = list_devices()
    if not devices:
        raise RuntimeError("没有检测到 iOS 设备。请用 USB 连接，并在设备上点「信任此电脑」。\n"
                           "  Windows 上还需要 Apple Mobile Device Service 在运行（装了 iTunes 即有）。")
    for bundle_id in CANDIDATE_IDS:
        info = app_info(bundle_id)
        if info:
            return bundle_id, info
    raise RuntimeError("设备上没有找到游戏。已尝试包名：" + "、".join(CANDIDATE_IDS))


def app_version(info: dict) -> str:
    return str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or "")


# --------------------------------------------------------------------------- 缓存定位

async def pick_catalog(device: Device, version: str) -> tuple[str, str]:
    """返回 (设备上的 catalog 路径, 文件名)。优先用与 app 版本同名的，否则取最新的。"""
    names = await device.ls(f"/Documents/{ADDR_REL}")
    catalogs = [n for n in names if re.fullmatch(r"catalog_.*\.json", n)]
    if not catalogs:
        raise RuntimeError(f"容器里找不到 catalog：/Documents/{ADDR_REL}")
    preferred = f"catalog_{version}.json"
    if preferred in catalogs:
        return f"/Documents/{ADDR_REL}/{preferred}", preferred
    best, best_time = None, -1.0
    for name in catalogs:
        stat = await device.stat(f"/Documents/{ADDR_REL}/{name}")
        try:
            when = float(stat.get("st_mtime") or 0)
        except (TypeError, ValueError):
            when = 0.0
        if when > best_time:
            best, best_time = name, when
    return f"/Documents/{ADDR_REL}/{best}", best


async def locate_bundle_dir(device: Device, inner_hash: str, state: dict,
                            quiet: bool = False) -> str | None:
    """外层目录名（Addressables 的 BundleName）不在 catalog 里，只能扫；结果记进 state。"""
    remembered = state.get("bundle_outer")
    if remembered:
        candidate = f"/Documents/{BUNDLES_REL}/{remembered}/{inner_hash}"
        if await device.exists(f"{candidate}/__data"):
            return candidate

    outers = await device.ls(f"/Documents/{BUNDLES_REL}")
    if not quiet:
        log(f"  扫描缓存定位代码包（{len(outers)} 个目录，首次会慢一点）…")
    for index, outer in enumerate(outers):
        try:
            children = await device.ls(f"/Documents/{BUNDLES_REL}/{outer}")
        except Exception:
            continue
        if inner_hash in children:
            state["bundle_outer"] = outer
            save_state(state)
            return f"/Documents/{BUNDLES_REL}/{outer}/{inner_hash}"
        if not quiet and (index + 1) % 400 == 0:
            log(f"    … {index + 1}/{len(outers)}")
    return None


# --------------------------------------------------------------------------- 注入器

def patcher_path() -> Path:
    name = "cesium-ios-patcher.exe" if os.name == "nt" else "cesium-ios-patcher"
    return TOOLS / "CesiumIosPatcher" / "bin" / "Release" / "net8.0" / name


def ensure_patcher() -> Path:
    exe = patcher_path()
    if exe.exists():
        return exe
    project = TOOLS / "CesiumIosPatcher"
    log("  注入器未编译，正在构建（需要 .NET 8 SDK）…")
    result = subprocess.run(["dotnet", "build", "-c", "Release", "--nologo", "-v", "m"],
                            cwd=project, capture_output=True, text=True)
    if result.returncode != 0 or not exe.exists():
        raise RuntimeError("注入器构建失败：\n" + (result.stdout or "") + (result.stderr or ""))
    return exe


def run_patcher(exe: Path, dll_in: Path, dll_out: Path, refs: Path) -> str:
    result = subprocess.run(
        [str(exe), "bootstrap", str(dll_in), str(dll_out),
         "--dir", LOADER_DIR, "--boot-dll", BOOT_DLL,
         "--boot-type", BOOT_TYPE, "--boot-method", BOOT_METHOD, "--boot-arg", "root",
         "--refs", str(refs)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError("注入失败：\n" + output)
    return output


# --------------------------------------------------------------------------- bundle 手术

def _import_bundle_tool():
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import bundle_assets  # noqa: E402
    return bundle_assets


def extract_assets(bundle: Path, outdir: Path) -> dict[str, bytes]:
    tool = _import_bundle_tool()
    outdir.mkdir(parents=True, exist_ok=True)
    items = tool.read_all(str(bundle))
    for name, data in items.items():
        (outdir / name).write_bytes(data)
    return items


def replace_asset(bundle: Path, asset: str, new_file: Path, out_bundle: Path) -> None:
    tool = _import_bundle_tool()
    out_bundle.parent.mkdir(parents=True, exist_ok=True)
    code = tool.cmd_replace(str(bundle), asset, str(new_file), str(out_bundle))
    if code != 0:
        raise RuntimeError("bundle 换回失败")


async def deploy_payload(device: Device, payload: Path, root: str) -> int:
    """把 payload 目录里的**内容**放进 <root>/（push 的语义是 <目标>/<目录名>）。"""
    sent = 0
    await device.makedirs(root)
    for child in sorted(payload.iterdir()):
        if child.name.startswith("."):
            continue
        await device.push(child, root)
        sent += 1
    return sent


# --------------------------------------------------------------------------- 模组管理

async def mod_inventory(device: Device, root: str) -> list[dict]:
    """列出 mods/ 与 disabled_mods/ 里的模组。状态只看目录，不看 sidecar 的 enabled。"""
    found: list[dict] = []
    for folder, enabled in (("mods", True), ("disabled_mods", False)):
        base = f"{root}/{folder}"
        if not await device.exists(base):
            continue
        for name in await device.ls(base):
            path = f"{base}/{name}"
            try:
                stat = await device.stat(path)
            except Exception:
                continue
            if stat.get("st_ifmt") != "S_IFDIR":
                continue
            entry: dict = {"id": name, "enabled": enabled, "dir": folder, "sidecar": None,
                           "has_config": False, "bytes": None}
            sidecar = f"{path}/{name}.json"
            if await device.exists(sidecar):
                try:
                    entry["sidecar"] = json.loads(
                        (await device.read(sidecar)).decode("utf-8-sig", "replace"))
                except Exception as error:  # noqa: BLE001
                    entry["sidecar"] = {"id": name, "name": name, "_parse_error": str(error)}
            entry["has_config"] = await device.exists(f"{path}/config.json")
            found.append(entry)
    return sorted(found, key=lambda m: m["id"].lower())


async def set_mod_enabled(device: Device, root: str, mod_id: str, enabled: bool) -> dict:
    """启停 = 在整个模组目录在两处之间搬移（搬完回读确认）。"""
    src_folder, dst_folder = ("disabled_mods", "mods") if enabled else ("mods", "disabled_mods")
    src = f"{root}/{src_folder}/{mod_id}"
    dst = f"{root}/{dst_folder}/{mod_id}"
    if not await device.exists(src):
        raise RuntimeError(f"在 {src_folder}/ 里找不到模组 {mod_id}")
    if await device.exists(dst):
        raise RuntimeError(f"{dst_folder}/ 里已经存在同名模组 {mod_id}，请先手工处理")
    await device.makedirs(f"{root}/{dst_folder}")
    await device.rename(src, dst)
    if not await device.exists(dst):
        raise RuntimeError("搬移后回读不到目标目录")
    return {"id": mod_id, "enabled": enabled, "dir": dst_folder}


async def locate_mod_dir(device: Device, root: str, mod_id: str) -> str:
    for folder in ("mods", "disabled_mods"):
        path = f"{root}/{folder}/{mod_id}"
        if await device.exists(path):
            return path
    raise RuntimeError(f"找不到模组目录 {mod_id}")


async def read_mod_config(device: Device, root: str, mod_id: str) -> dict:
    path = await locate_mod_dir(device, root, mod_id)
    config = f"{path}/config.json"
    if not await device.exists(config):
        return {"id": mod_id, "path": config, "text": "", "exists": False}
    return {"id": mod_id, "path": config, "exists": True,
            "text": (await device.read(config)).decode("utf-8-sig", "replace")}


async def write_mod_config(device: Device, root: str, mod_id: str, text: str) -> dict:
    """整段文本写回，保存前必须能解析回 JSON 对象（保留注释与原有写法，不重新序列化）。"""
    try:
        parsed = json.loads(text)
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(f"配置不是合法 JSON：{error}") from None
    if not isinstance(parsed, dict):
        raise RuntimeError("配置的顶层必须是 JSON 对象")
    path = await locate_mod_dir(device, root, mod_id)
    await device.write(f"{path}/config.json", text.encode("utf-8"))
    readback = (await device.read(f"{path}/config.json")).decode("utf-8-sig", "replace")
    if readback != text:
        raise RuntimeError("回读内容与写入不一致")
    return {"id": mod_id, "path": f"{path}/config.json", "bytes": len(text.encode("utf-8"))}


async def list_logs(device: Device, root: str) -> list[dict]:
    base = f"{root}/logs"
    if not await device.exists(base):
        return []
    out: list[dict] = []
    for name in await device.ls(base):
        item = {"name": name, "bytes": None, "mtime": ""}
        try:
            stat = await device.stat(f"{base}/{name}")
            item["bytes"] = stat.get("st_size")
            item["mtime"] = str(stat.get("st_mtime") or "")
        except Exception:
            pass
        out.append(item)
    return sorted(out, key=lambda x: x["name"], reverse=True)


async def read_log(device: Device, root: str, name: str) -> str:
    if "/" in name or "\\" in name or name.startswith("."):
        raise RuntimeError("非法日志名")
    return (await device.read(f"{root}/logs/{name}")).decode("utf-8", "replace")


# --------------------------------------------------------------------------- 检测

async def collect(device: Device, version: str, state: dict) -> dict:
    report: dict = {"bundle_id": device.bundle_id, "app_version": version, "issues": []}

    catalog_remote, catalog_name = await pick_catalog(device, version)
    report["catalog"] = catalog_name
    local_dir = WORK_DIR / "catalog"
    local_dir.mkdir(parents=True, exist_ok=True)
    local_catalog = local_dir / catalog_name
    await device.pull(catalog_remote, local_catalog)
    report["catalog_sha256"] = sha256_file(local_catalog)

    catalog = Catalog(local_catalog)
    report["catalog_build_hash"] = catalog.build_result_hash
    inner = catalog.bundle_hash_for(ASSET_NAME)
    if not inner:
        report["issues"].append("catalog 里找不到 AstralParty.Runtime.dll 的位置")
        return report
    report["code_bundle_hash"] = inner

    bundle_dir = await locate_bundle_dir(device, inner, state)
    if not bundle_dir:
        report["issues"].append("缓存里找不到当前代码包（热更可能没下完）")
        return report
    report["bundle_dir"] = bundle_dir

    stat = await device.stat(f"{bundle_dir}/__data")
    report["bundle_bytes"] = stat.get("st_size")
    report["bundle_mtime"] = stat.get("st_mtime")

    # 每次都重新取回来算 SHA-256。AFC 自带的 get_file_hash 是 SHA-1，不能拿来和本地
    # 算的 SHA-256 比；而且游戏可能已经换过这个文件，不能复用本地旧副本。
    local_bundle = WORK_DIR / "current" / f"{inner}.data"
    await device.pull(f"{bundle_dir}/__data", local_bundle)
    current_hash = sha256_file(local_bundle)
    report["bundle_sha256"] = current_hash

    injected = False
    try:
        assets = extract_assets(local_bundle, WORK_DIR / "current" / inner)
        dll = assets.get(ASSET_NAME, b"")
        injected = PATCH_MARKER in dll or PATCH_MARKER_UTF16 in dll
        report["asset_count"] = len(assets)
        report["injected"] = injected
        report["runtime_dll_bytes"] = len(dll)
        report["runtime_dll_sha256"] = sha256_bytes(dll)
    except Exception as error:  # noqa: BLE001
        report["issues"].append(f"解包失败：{error}")

    recorded = (state.get("installed") or {})
    if recorded.get("inner") == inner and recorded.get("patched_sha256") == current_hash:
        report["patch_state"] = "patched"
    elif recorded.get("inner") == inner and recorded.get("original_sha256") == current_hash:
        report["patch_state"] = "clean"
    elif injected:
        report["patch_state"] = "patched-external"
    else:
        report["patch_state"] = "unknown"

    # 加载器
    root = f"/Documents/{LOADER_DIR}"
    loader: dict = {"root": root}
    if not await device.exists(root):
        loader["present"] = False
        report["issues"].append("容器里没有 CesiumLoader 目录")
    else:
        loader["present"] = True
        entries = await device.ls(root)
        loader["entries"] = entries
        loader["has_bootstrap"] = BOOT_DLL in entries
        loader["has_api"] = "CesiumAndroidApi.dll" in entries
        mods_dir = f"{root}/mods"
        mods = await device.ls(mods_dir) if await device.exists(mods_dir) else []
        loader["mods"] = mods
        loader["mod_count"] = len(mods)
        logs_dir = f"{root}/logs"
        logs = await device.ls(logs_dir) if await device.exists(logs_dir) else []
        loader["logs"] = logs[-6:]
        latest = next((n for n in reversed(logs) if n.startswith("bootstrap-") and n.endswith(".log")), None)
        if latest:
            text = (await device.read(f"{logs_dir}/{latest}")).decode("utf-8", "replace")
            loader["bootstrap_log"] = latest
            loader["bootstrap_tail"] = text.strip().splitlines()[-12:]
            match = re.search(r"done: ok=(\d+) failed=(\d+)", text)
            if match:
                loader["mods_ok"] = int(match.group(1))
                loader["mods_failed"] = int(match.group(2))
        errors = [n for n in logs if n.startswith("mod-errors")]
        if errors:
            loader["mod_errors_log"] = errors[-1]
    report["loader"] = loader

    # 注入标记文件（bring-up 用；正式形态可能没有）
    markers = [n for n in await device.ls("/Documents") if n.startswith("cesium_")]
    report["markers"] = sorted(markers)
    report["issues"] = report["issues"]
    return report


def print_report(report: dict) -> None:
    section("设备")
    log(f"  包名        : {report['bundle_id']}")
    log(f"  游戏版本    : {report.get('app_version') or '?'}")

    section("资源 catalog")
    log(f"  文件        : {report.get('catalog')}")
    log(f"  build hash  : {report.get('catalog_build_hash')}")
    log(f"  代码包哈希  : {report.get('code_bundle_hash')}")

    section("热更缓存里的代码包")
    log(f"  目录        : {report.get('bundle_dir')}")
    log(f"  大小        : {report.get('bundle_bytes')} B")
    log(f"  sha256      : {report.get('bundle_sha256')}")
    log(f"  内含资产    : {report.get('asset_count')} 个")
    log(f"  Runtime.dll : {report.get('runtime_dll_bytes')} B  {report.get('runtime_dll_sha256')}")
    state = report.get("patch_state")
    label = {
        "patched": "已注入",
        "clean": "未注入（原始包，与本工具记录一致）",
        "patched-external": "已注入（非本工具安装，无本地记录）",
        "unknown": "未知（与本工具记录不符，可能游戏刚热更过）",
    }.get(state, "?")
    log(f"  补丁状态    : {label}（程序集内标记：{'有' if report.get('injected') else '无'}）")

    loader = report.get("loader") or {}
    section("加载器")
    if not loader.get("present"):
        log("  未安装")
    else:
        log(f"  根目录      : {loader['root']}")
        log(f"  引导 DLL    : {'有' if loader.get('has_bootstrap') else '缺'}")
        log(f"  安卓 API    : {'有' if loader.get('has_api') else '无'}")
        log(f"  模组        : {loader.get('mod_count', 0)} 个")
        if loader.get("mods"):
            log("                " + "、".join(loader["mods"][:12]) + ("…" if len(loader["mods"]) > 12 else ""))
        if loader.get("mods_ok") is not None:
            log(f"  上次启动    : ok={loader['mods_ok']} failed={loader.get('mods_failed', 0)}")
        if loader.get("bootstrap_log"):
            log(f"  引导日志    : {loader['bootstrap_log']}")
            for line in loader.get("bootstrap_tail") or []:
                log(f"                {line}")
        if loader.get("mod_errors_log"):
            warn(f"存在模组错误日志：{loader['mod_errors_log']}")

    if report.get("markers"):
        section("注入标记")
        log("  " + "、".join(report["markers"]))

    if report.get("issues"):
        section("问题")
        for issue in report["issues"]:
            bad(issue)


# --------------------------------------------------------------------------- 命令

async def do_detect(as_json: bool) -> int:
    bundle_id, info = find_game()
    device, session = await open_device(bundle_id)
    try:
        state = load_state()
        report = await collect(device, app_version(info), state)
    finally:
        await close_device(session)
    if as_json:
        # pymobiledevice3 的 stat 会把 st_mtime 解析成 datetime，故 default=str
        log(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print_report(report)
    return 0 if not report.get("issues") else 2


async def do_install(payload: Path | None, skip_payload: bool, skip_patch: bool) -> int:
    bundle_id, info = find_game()
    version = app_version(info)
    device, session = await open_device(bundle_id)
    try:
        state = load_state()
        section("定位")
        catalog_remote, catalog_name = await pick_catalog(device, version)
        local_catalog = WORK_DIR / "catalog" / catalog_name
        await device.pull(catalog_remote, local_catalog)
        catalog = Catalog(local_catalog)
        inner = catalog.bundle_hash_for(ASSET_NAME)
        if not inner:
            bad("catalog 里找不到 AstralParty.Runtime.dll")
            return 1
        ok(f"catalog {catalog_name}（build {catalog.build_result_hash}）")
        ok(f"代码包哈希 {inner}")

        bundle_dir = await locate_bundle_dir(device, inner, state)
        if not bundle_dir:
            bad("缓存里找不到当前代码包，先把游戏启动一次让热更下完")
            return 1
        ok(f"代码包目录 {bundle_dir}")

        origin = WORK_DIR / "install" / f"{inner}.orig"
        await device.pull(f"{bundle_dir}/__data", origin)
        original_hash = sha256_file(origin)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, BACKUP_DIR / f"{inner}.data")
        ok(f"已备份原始包 -> backups/{inner}.data  {original_hash[:16]}…")

        if not skip_patch:
            section("注入")
            exe = ensure_patcher()
            assets = WORK_DIR / "install" / inner
            items = extract_assets(origin, assets)
            if ASSET_NAME not in items:
                bad(f"包里没有 {ASSET_NAME}")
                return 1
            patched = WORK_DIR / "install" / f"{inner}.patched.dll"
            output = run_patcher(exe, assets / ASSET_NAME, patched, assets)
            for line in output.strip().splitlines():
                log("  " + line)
            out_bundle = WORK_DIR / "install" / f"{inner}.patched.data"
            replace_asset(origin, ASSET_NAME, patched, out_bundle)

            after = extract_assets(out_bundle, WORK_DIR / "install" / f"{inner}.check")
            changed = [n for n in items if after.get(n) != items[n]]
            if changed != [ASSET_NAME]:
                bad(f"完整性校验异常，被改动的资产：{changed}")
                return 1
            ok(f"其余 {len(items) - 1} 个资产字节一致")

            await device.write(f"{bundle_dir}/__data", out_bundle.read_bytes())
            readback = WORK_DIR / "install" / f"{inner}.readback.data"
            await device.pull(f"{bundle_dir}/__data", readback)
            expect = sha256_file(out_bundle)
            if sha256_file(readback) != expect:
                bad("回读校验不一致，写入可能失败")
                return 1
            ok(f"已写入代码包并回读校验  {expect[:16]}…")
            state["installed"] = {
                "inner": inner, "outer": state.get("bundle_outer"),
                "original_sha256": original_hash, "patched_sha256": expect,
                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            save_state(state)

        if not skip_payload:
            section("载荷")
            if payload is None or not payload.is_dir():
                bad(f"载荷目录不存在：{payload}")
                return 1
            sent = await deploy_payload(device, payload, f"/Documents/{LOADER_DIR}")
            ok(f"已投放 {sent} 项 -> /Documents/{LOADER_DIR}")
    finally:
        await close_device(session)

    section("完成")
    log("  现在完全退出游戏并重新启动；用 `detect` 查看加载结果。")
    return 0


async def do_restore(remove_loader: bool) -> int:
    bundle_id, info = find_game()
    device, session = await open_device(bundle_id)
    try:
        state = load_state()
        catalog_remote, catalog_name = await pick_catalog(device, app_version(info))
        local_catalog = WORK_DIR / "catalog" / catalog_name
        await device.pull(catalog_remote, local_catalog)
        inner = Catalog(local_catalog).bundle_hash_for(ASSET_NAME)
        bundle_dir = await locate_bundle_dir(device, inner, state)
        if not bundle_dir:
            bad("缓存里找不到代码包")
            return 1

        backup = BACKUP_DIR / f"{inner}.data"
        if backup.exists():
            await device.write(f"{bundle_dir}/__data", backup.read_bytes())
            ok(f"已用备份还原代码包（{sha256_file(backup)[:16]}…）")
        else:
            await device.rm(bundle_dir)
            ok("本地没有备份，已删除缓存条目 —— 下次启动游戏会重新下载原始包")

        if remove_loader:
            if await device.exists(f"/Documents/{LOADER_DIR}"):
                await device.rm(f"/Documents/{LOADER_DIR}")
                ok(f"已删除 /Documents/{LOADER_DIR}")
            for name in await device.ls("/Documents"):
                if name.startswith("cesium_"):
                    await device.rm(f"/Documents/{name}")
            ok("已清理注入标记")

        state.pop("installed", None)
        save_state(state)
    finally:
        await close_device(session)
    return 0


def resolve_payload(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    default = ROOT / "payload" / LOADER_DIR
    return default if default.is_dir() else None


# --------------------------------------------------------------------------- 交互

MENU = """
=== CesiumLoader iOS ===
  1) 检测（设备 / 游戏 / catalog / 缓存 / 加载器 / 补丁状态）
  2) 安装或更新（注入代码包 + 投放载荷）
  3) 仅注入代码包
  4) 仅投放载荷
  5) 还原代码包（保留加载器）
  6) 完全卸载（还原 + 删除加载器）
  0) 退出
"""


def interactive() -> int:
    check_dependencies()
    payload = resolve_payload(None)
    while True:
        print(MENU)
        if payload:
            print(f"载荷目录: {payload}")
        else:
            print("载荷目录: 未找到（放到 payload/CesiumLoader/ 或用 --payload 指定）")
        choice = input("选择> ").strip()
        if choice in ("0", "q", "quit", "exit"):
            return 0
        try:
            if choice == "1":
                asyncio.run(do_detect(False))
            elif choice == "2":
                if payload is None:
                    entered = input("载荷目录路径> ").strip()
                    payload = Path(entered).expanduser().resolve() if entered else None
                print(f"安装完成: {asyncio.run(do_install(payload, False, False)) == 0}")
            elif choice == "3":
                print(f"注入完成: {asyncio.run(do_install(payload, True, False)) == 0}")
            elif choice == "4":
                if payload is None:
                    entered = input("载荷目录路径> ").strip()
                    payload = Path(entered).expanduser().resolve() if entered else None
                print(f"投放完成: {asyncio.run(do_install(payload, False, True)) == 0}")
            elif choice == "5":
                asyncio.run(do_restore(False))
            elif choice == "6":
                confirm = input("确认完全卸载？会还原代码包并删除加载器目录 [y/N]> ").strip().lower()
                if confirm == "y":
                    asyncio.run(do_restore(True))
            else:
                warn("无效选择")
        except KeyboardInterrupt:
            print()
        except Exception as error:  # noqa: BLE001
            bad(str(error))


# --------------------------------------------------------------------------- 入口

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("detect", help="检测设备、游戏、缓存与加载器状态")
    p.add_argument("--json", action="store_true", help="输出机器可读的 JSON")

    p = sub.add_parser("install", help="注入代码包并投放载荷")
    p.add_argument("--payload", help=f"载荷目录（默认 {ROOT / 'payload' / LOADER_DIR}）")
    p.add_argument("--skip-payload", action="store_true", help="只注入，不投放载荷")
    p.add_argument("--skip-patch", action="store_true", help="只投放载荷，不注入")

    p = sub.add_parser("restore", help="还原代码包")
    p.add_argument("--keep-loader", action="store_true", help="保留加载器目录")

    sub.add_parser("uninstall", help="还原代码包并删除加载器目录")

    args = parser.parse_args()
    try:
        if args.command:
            check_dependencies()
        if args.command == "detect":
            return asyncio.run(do_detect(args.json))
        if args.command == "install":
            return asyncio.run(do_install(resolve_payload(args.payload),
                                          args.skip_payload, args.skip_patch))
        if args.command == "restore":
            return asyncio.run(do_restore(not args.keep_loader))
        if args.command == "uninstall":
            return asyncio.run(do_restore(True))
        return interactive()
    except KeyboardInterrupt:
        return 130
    except RuntimeError as error:
        bad(str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
