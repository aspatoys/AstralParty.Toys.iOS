"""Addressables catalog —— 解析 catalog、定位承载代码包的 bundle。"""

from __future__ import annotations

from pathlib import Path
import base64
import json
import re
import struct

from .common import save_state
from .device import Device
from .output import log
from .paths import ADDR_REL, BUNDLES_REL

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
