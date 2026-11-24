"""检测报告 —— 汇总设备/游戏/catalog/缓存/加载器/补丁状态。"""

from __future__ import annotations

import re

from .catalog import Catalog, locate_bundle_dir, pick_catalog
from .common import sha256_bytes, sha256_file
from .device import Device
from .patcher import extract_assets
from .payload import resolve_payload
from .paths import (ASSET_NAME, BOOT_DLL, BOOT_TYPE, LEGACY_BOOT_DLL, LEGACY_BOOT_TYPE,
                    LOADER_DIR, patch_with_current_type, patch_with_legacy_type, pick_api,
                    pick_bootstrap, ROOT, WORK_DIR)

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
    # stat 的 st_mtime 是 datetime，直接返回会让 GUI 的 JSON 序列化炸掉
    report["bundle_mtime"] = str(stat.get("st_mtime") or "")

    # 每次都重新取回来算 SHA-256。AFC 自带的 get_file_hash 是 SHA-1，不能拿来和本地
    # 算的 SHA-256 比；而且游戏可能已经换过这个文件，不能复用本地旧副本。
    local_bundle = WORK_DIR / "current" / f"{inner}.data"
    await device.pull(f"{bundle_dir}/__data", local_bundle)
    current_hash = sha256_file(local_bundle)
    report["bundle_sha256"] = current_hash

    injected = False
    stale = False
    try:
        assets = extract_assets(local_bundle, WORK_DIR / "current" / inner)
        dll = assets.get(ASSET_NAME, b"")
        injected = patch_with_current_type(dll)
        stale = patch_with_legacy_type(dll)
        if stale:
            report["issues"].append(
                f"代码包里的补丁烧的是旧引导类型名 {LEGACY_BOOT_TYPE} —— "
                f"需重新注入（新载荷找 {BOOT_DLL} / {BOOT_TYPE}，旧补丁加载不到引导）")
        report["asset_count"] = len(assets)
        report["injected"] = injected
        report["patch_stale"] = stale
        report["runtime_dll_bytes"] = len(dll)
        report["runtime_dll_sha256"] = sha256_bytes(dll)
    except Exception as error:  # noqa: BLE001
        report["issues"].append(f"解包失败：{error}")

    recorded = (state.get("installed") or {})
    if recorded.get("inner") == inner and recorded.get("patched_sha256") == current_hash:
        report["patch_state"] = "patched"
    elif recorded.get("inner") == inner and recorded.get("original_sha256") == current_hash:
        report["patch_state"] = "clean"
    elif stale:
        report["patch_state"] = "stale"
    elif injected:
        report["patch_state"] = "patched-external"
    else:
        report["patch_state"] = "unknown"

    # 加载器
    root = f"/Documents/{LOADER_DIR}"
    local_payload = resolve_payload(None)
    payload_dir = ROOT / "payload" / LOADER_DIR
    loader: dict = {"root": root, "payload": str(local_payload or payload_dir),
                    "payload_present": local_payload is not None}
    if not await device.exists(root):
        loader["present"] = False
        if local_payload is None:
            report["issues"].append(
                f"容器里没有 CesiumLoader 目录，本机也没有载荷目录 {payload_dir} —— "
                "到「设置」→「维护」点「拉取最新 CesiumLoader」"
                "（或自己把载荷放进该目录），再点右上角「一键安装」")
        else:
            report["issues"].append(
                f"容器里没有 CesiumLoader 目录 —— 点右上角「一键安装」把 {local_payload} 投放上去")
    else:
        loader["present"] = True
        entries = await device.ls(root)
        loader["entries"] = entries
        bootstrap = pick_bootstrap(entries)
        loader["bootstrap_dll"] = bootstrap
        loader["has_bootstrap"] = bootstrap is not None
        loader["bootstrap_stale"] = bootstrap == LEGACY_BOOT_DLL
        if loader["bootstrap_stale"]:
            report["issues"].append(
                f"引导 DLL 还是旧名 {LEGACY_BOOT_DLL} —— 需重装一次加载器（新名 {BOOT_DLL}）")
        loader["has_api"] = pick_api(entries) is not None
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
