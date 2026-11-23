#!/usr/bin/env python3
"""扫描 iOS 游戏容器里的 Addressables 缓存，并与一份 catalog 对账。

    python scan_cache.py <catalog.json> [--out cache.json]

输出：
  - 外层目录数（= BundleName）与每个外层下的内层目录（= 内容哈希）
  - catalog 的远端 bundle 哪些在缓存里 / 哪些缺失（缺失=热更没下完）
  - 缓存里有多少陈旧条目（不在该 catalog 里）

用途：热更之后重新定位代码 bundle（bundle 哈希每次都变），以及判断热更是否完成。

    uv run tools/scan_cache.py catalog_3.3.0.json
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["pymobiledevice3>=11.63"]
# ///

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.house_arrest import HouseArrestService

BUNDLE = "com.feimo.astralpartycn"
CACHE = "/Documents/com.unity.addressables/AssetBundles"


def catalog_sets(path: str) -> tuple[set[str], set[str], str]:
    d = json.load(open(path, encoding="utf-8"))
    remote, local = set(), set()
    for x in d["m_InternalIds"]:
        m = re.search(r"/([0-9a-f]{32})\.bundle$", x) or re.search(r"\\([0-9a-f]{32})\.bundle$", x)
        if not m:
            continue
        (remote if "WebServerConfig" in x else local).add(m.group(1))
    return remote, local, d.get("m_BuildResultHash", "")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("catalog")
    ap.add_argument("--bundle", default=BUNDLE)
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    remote, local, brh = catalog_sets(args.catalog)

    lockdown = await create_using_usbmux(autopair=True)
    try:
        async with await HouseArrestService.create(lockdown, args.bundle, documents_only=True) as afc:
            outers = sorted(await afc.listdir(args.cache))
            print(f"outer dirs: {len(outers)}", file=sys.stderr)
            mapping: dict[str, list[str]] = {}
            for i, o in enumerate(outers):
                try:
                    kids = sorted(await afc.listdir(f"{args.cache}/{o}"))
                except Exception as exc:  # noqa: BLE001
                    kids = [f"<error {exc}>"]
                mapping[o] = kids
                if (i + 1) % 500 == 0:
                    print(f"  … {i + 1}/{len(outers)}", file=sys.stderr)
    finally:
        await lockdown.close()

    inner = {k for kids in mapping.values() for k in kids}
    print(f"catalog         : {args.catalog}")
    print(f"catalog build   : {brh}")
    print(f"outer dirs      : {len(mapping)}")
    print(f"inner dirs      : {len(inner)}")
    print(f"remote in catalog: {len(remote)}   present: {len(inner & remote)}   MISSING: {len(remote - inner)}")
    print(f"stale in cache  : {len(inner - remote - local)}")
    print(f"local in cache  : {len(inner & local)}  (应为 0)")
    missing = sorted(remote - inner)
    if missing:
        print("--- missing remote bundles (热更未完成) ---")
        for h in missing[:40]:
            print(f"  {h}")
    multi = {o: k for o, k in mapping.items() if len(k) > 1}
    if multi:
        print(f"--- 外层目录下有多个内层（{len(multi)} 个，通常是版本残留）---")
        for o, k in list(multi.items())[:10]:
            print(f"  {o}: {k}")

    if args.out:
        json.dump({"catalog": args.catalog, "build_result_hash": brh, "map": mapping},
                  open(args.out, "w", encoding="utf-8"), indent=1)
        print(f"map -> {args.out}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
