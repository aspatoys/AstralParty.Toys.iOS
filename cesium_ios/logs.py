"""日志 —— 列日志、读日志。"""

from __future__ import annotations

from .common import stamp
from .device import Device

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
            item["mtime"] = stamp(stat.get("st_mtime"))
        except Exception:
            pass
        out.append(item)
    return sorted(out, key=lambda x: x["name"], reverse=True)


async def read_log(device: Device, root: str, name: str) -> str:
    if "/" in name or "\\" in name or name.startswith("."):
        raise RuntimeError("非法日志名")
    return (await device.read(f"{root}/logs/{name}")).decode("utf-8", "replace")
