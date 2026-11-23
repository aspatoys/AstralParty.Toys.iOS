#!/usr/bin/env python3
"""iOS 游戏容器的 AFC 通道（house_arrest），免越狱读写。

这是安卓侧 Shizuku/shell 通道在 iOS 上的对应物：
`com.apple.mobile.house_arrest` 把某个已安装 app 的容器「出租」给桌面端，
默认是**整个容器**（Documents / Library / tmp），加 `--documents` 只拿 Documents。

    python ios_afc.py --help
    python ios_afc.py info
    python ios_afc.py ls /
    python ios_afc.py ls /Documents
    python ios_afc.py walk /Documents/com.unity.addressables --limit 40
    python ios_afc.py stat /Documents/com.unity.addressables/AssetBundles/…/__data
    python ios_afc.py get  <remote> <local>
    python ios_afc.py put  <local>  <remote>
    python ios_afc.py rm   <remote>

`get` / `put` 对目录是递归的（走 `AfcService.pull` / `push`）。

    uv run tools/ios_afc.py ls /Documents
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["pymobiledevice3>=11.63"]
# ///

from __future__ import annotations

import argparse
import asyncio
import sys

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.house_arrest import HouseArrestService

DEFAULT_BUNDLE = "com.feimo.astralpartycn"


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n}{unit}" if unit == "B" else f"{n/1:.1f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}GB"


async def act(args) -> int:
    lockdown = await create_using_usbmux(serial=args.serial, autopair=True)
    try:
        async with await HouseArrestService.create(
            lockdown, args.bundle, documents_only=args.documents
        ) as afc:
            if args.command == "info":
                info = await afc.get_device_info()
                print(f"bundle    : {args.bundle}")
                print(f"rooted at : {args.root or '/'}  (documents_only={args.documents})")
                for k in ("Model", "FSTotalBytes", "FSFreeBytes", "FSBlockSize"):
                    if k in info:
                        print(f"{k:10}: {info[k]}")
                return 0

            if args.command == "ls":
                names = sorted(await afc.listdir(args.remote))
                if args.long:
                    for n in names:
                        p = args.remote.rstrip("/") + "/" + n
                        try:
                            st = await afc.stat(p)
                            kind = "d" if st.get("st_ifmt") == "S_IFDIR" else "-"
                            print(f"{kind} {st.get('st_size', 0):>12}  {n}")
                        except Exception as exc:  # noqa: BLE001
                            print(f"? {'':>12}  {n}   ({exc})")
                else:
                    for n in names:
                        print(n)
                print(f"# {len(names)} entries", file=sys.stderr)
                return 0

            if args.command == "walk":
                count = 0
                async for dirpath, dirnames, filenames in afc.walk(args.remote):
                    for f in filenames:
                        count += 1
                        if count > args.limit:
                            print(f"# … stopped at limit {args.limit}", file=sys.stderr)
                            return 0
                        print(f"{dirpath.rstrip('/')}/{f}")
                    if count > args.limit:
                        return 0
                print(f"# {count} files", file=sys.stderr)
                return 0

            if args.command == "stat":
                st = await afc.stat(args.remote)
                for k, v in st.items():
                    print(f"{k:14}: {v}")
                return 0

            if args.command == "exists":
                print("yes" if await afc.exists(args.remote) else "no")
                return 0 if await afc.exists(args.remote) else 1

            if args.command == "get":
                await afc.pull(args.remote, args.local)
                print(f"pulled {args.remote} -> {args.local}")
                return 0

            if args.command == "put":
                await afc.push(args.local, args.remote)
                print(f"pushed {args.local} -> {args.remote}")
                return 0

            if args.command == "rm":
                await afc.rm(args.remote)
                print(f"removed {args.remote}")
                return 0

            print(f"unknown command {args.command}", file=sys.stderr)
            return 2
    finally:
        await lockdown.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bundle", default=DEFAULT_BUNDLE, help=f"bundle id (default {DEFAULT_BUNDLE})")
    p.add_argument("--serial", default=None, help="device UDID (default: only connected device)")
    p.add_argument("--documents", action="store_true",
                   help="vend Documents only instead of the whole container")
    p.add_argument("--root", default=None, help="informational: where the AFC session is rooted")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("info")
    ls = sub.add_parser("ls")
    ls.add_argument("remote", nargs="?", default="/")
    ls.add_argument("--long", action="store_true", help="stat each entry")
    wk = sub.add_parser("walk")
    wk.add_argument("remote", nargs="?", default="/")
    wk.add_argument("--limit", type=int, default=200)
    st = sub.add_parser("stat")
    st.add_argument("remote")
    ex = sub.add_parser("exists")
    ex.add_argument("remote")
    g = sub.add_parser("get")
    g.add_argument("remote")
    g.add_argument("local")
    pu = sub.add_parser("put")
    pu.add_argument("local")
    pu.add_argument("remote")
    rm = sub.add_parser("rm")
    rm.add_argument("remote")

    args = p.parse_args()
    try:
        return asyncio.run(act(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
