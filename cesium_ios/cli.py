"""命令行 —— argparse、交互式菜单、打印报告。"""

from __future__ import annotations

from pathlib import Path
import argparse
import asyncio
import json

from .common import load_state
from .device import app_version, check_dependencies, close_device, find_game, open_device
from .install import do_install, do_restore
from .output import bad, log, section, set_log_prefix, warn
from .paths import LOADER_DIR, ROOT
from .payload import resolve_payload
from .release import pull_latest
from .report import collect

MENU = """
=== AstralParty.Toys.iOS ===
  1) 检测（设备 / 游戏 / catalog / 缓存 / 加载器 / 补丁状态）
  2) 安装或更新（注入代码包 + 投放载荷）
  3) 仅注入代码包
  4) 仅投放载荷
  5) 还原代码包（保留加载器）
  6) 完全卸载（还原 + 删除加载器）
  0) 退出
"""


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
        "stale": "已过期（补丁里是旧引导类型名，需重新注入）",
        "unknown": "未知（与本工具记录不符，可能游戏刚热更过）",
    }.get(state, "?")
    log(f"  补丁状态    : {label}（程序集内标记：{'有' if report.get('injected') else '无'}"
        + ("，旧名补丁" if report.get("patch_stale") else "") + "）")

    loader = report.get("loader") or {}
    section("加载器")
    if not loader.get("present"):
        log("  未安装")
    else:
        log(f"  根目录      : {loader['root']}")
        bootstrap_state = ("有（旧名，需重装）" if loader.get("bootstrap_stale")
                           else "有" if loader.get("has_bootstrap") else "缺")
        log(f"  引导 DLL    : {bootstrap_state}")
        log(f"  移动 API    : {'有' if loader.get('has_api') else '无'}")
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


def main() -> int:
    set_log_prefix("cli")  # 本次运行的输出写 logs/cli-<时间戳>.log
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "AstralParty.Toys.iOS —— 免越狱给 iOS 版《吉星派对》装 CesiumLoader：\n"
            "改写容器里的热更代码包注入引导，再把载荷投放到 <Documents>/CesiumLoader/。\n"
            "不带子命令时进交互式菜单。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("detect", help="检测设备、游戏、缓存与加载器状态")
    p.add_argument("--json", action="store_true", help="输出机器可读的 JSON")

    p = sub.add_parser("install", help="注入代码包并投放载荷")
    p.add_argument("--payload", help=f"载荷目录（默认 {ROOT / 'payload' / LOADER_DIR}）")
    p.add_argument("--skip-payload", action="store_true", help="只注入，不投放载荷")
    p.add_argument("--skip-patch", action="store_true", help="只投放载荷，不注入")

    p = sub.add_parser("restore", help="还原代码包")
    p.add_argument("--keep-loader", action="store_true", help="保留加载器目录")

    p = sub.add_parser("pull", help="从官方 Release 拉取最新加载器载荷（SDK + 模组 + 安卓引导）")
    p.add_argument("--payload", help=f"载荷目录（默认 {ROOT / 'payload' / LOADER_DIR}）")
    p.add_argument("--no-android", action="store_true", help="只拉 SDK 与模组，不碰安卓引导 DLL")
    p.add_argument("--force-android", action="store_true", help="已有引导 DLL 也从安卓包重新取")

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
        if args.command == "pull":
            target = Path(args.payload).expanduser().resolve() if args.payload else None
            summary = pull_latest(target, with_android=not args.no_android,
                                  force_android=args.force_android, progress=log)
            log("")
            log(f"  载荷目录 : {summary['payload']}")
            log(f"  版本     : {summary['version']}（{summary.get('releaseTag') or ''}）")
            log(f"  模组     : {len(summary['mods'])} 个")
            log(f"  引导 DLL : {summary['android']['bootstrap']}")
            log(f"  悬浮窗API: {summary['android']['android_api']}")
            return 2 if summary["missing"] else 0
        if args.command == "uninstall":
            return asyncio.run(do_restore(True))
        return interactive()
    except KeyboardInterrupt:
        return 130
    except RuntimeError as error:
        bad(str(error))
        return 1


if __name__ == "__main__":  # 也支持 `uv run python -m cesium_ios.cli`
    raise SystemExit(main())
