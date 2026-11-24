"""模组 —— 模组清单、启停（搬目录）、config.json 读写。"""

from __future__ import annotations

import json

from .device import Device

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


async def locate_mod_dir(device: Device, root: str, mod_id: str, folder: str | None = None) -> str:
    """定位模组目录。folder 是已知目录名时直接命中，省掉两次 exists 往返。"""
    if folder in ("mods", "disabled_mods"):
        path = f"{root}/{folder}/{mod_id}"
        if await device.exists(path):
            return path
    for name in ("mods", "disabled_mods"):
        path = f"{root}/{name}/{mod_id}"
        if await device.exists(path):
            return path
    raise RuntimeError(f"找不到模组目录 {mod_id}")


async def read_mod_config(device: Device, root: str, mod_id: str,
                          folder: str | None = None) -> dict:
    path = await locate_mod_dir(device, root, mod_id, folder)
    config = f"{path}/config.json"
    if not await device.exists(config):
        return {"id": mod_id, "path": config, "text": "", "exists": False}
    return {"id": mod_id, "path": config, "exists": True,
            "text": (await device.read(config)).decode("utf-8-sig", "replace")}


async def write_mod_config(device: Device, root: str, mod_id: str, text: str,
                           folder: str | None = None) -> dict:
    """整段文本写回，保存前必须能解析回 JSON 对象（保留注释与原有写法，不重新序列化）。"""
    try:
        parsed = json.loads(text)
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(f"配置不是合法 JSON：{error}") from None
    if not isinstance(parsed, dict):
        raise RuntimeError("配置的顶层必须是 JSON 对象")
    path = await locate_mod_dir(device, root, mod_id, folder)
    await device.write(f"{path}/config.json", text.encode("utf-8"))
    readback = (await device.read(f"{path}/config.json")).decode("utf-8-sig", "replace")
    if readback != text:
        raise RuntimeError("回读内容与写入不一致")
    return {"id": mod_id, "path": f"{path}/config.json", "bytes": len(text.encode("utf-8"))}
