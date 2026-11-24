"""安装/还原流程 —— 给 CLI 与 GUI 共用的高层流程。"""

from __future__ import annotations

from pathlib import Path
import shutil
import time

from .catalog import Catalog, locate_bundle_dir, pick_catalog
from .common import load_state, save_state, sha256_file
from .device import app_version, close_device, find_game, open_device
from .output import bad, log, ok, section
from .patcher import ensure_patcher, extract_assets, replace_asset, run_patcher
from .paths import ASSET_NAME, BACKUP_DIR, LOADER_DIR, ROOT, WORK_DIR
from .payload import deploy_payload

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
                bad("载荷目录不存在："
                    + (str(payload) if payload else
                       f"{ROOT / 'payload' / LOADER_DIR}"
                       "（把加载器发行包解开到这里，见 README「载荷布局」）"))
                return 1
            result = await deploy_payload(device, payload, f"/Documents/{LOADER_DIR}")
            ok(f"已投放 {result['sent']} 项 -> /Documents/{LOADER_DIR}"
               + (f"（跳过 {result['skipped']} 个非运行时文件）" if result['skipped'] else ""))
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
