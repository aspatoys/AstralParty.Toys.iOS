"""卡面 —— skins/ 方案的列出、导入、启用。"""

from __future__ import annotations

from pathlib import Path
import json
import re
import shutil

from .common import zip_members
from .device import Device
from .paths import WORK_DIR

SKIN_MOD_ID = "CardSkinMod"


SKIN_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,32}$")


async def skins_list(device: Device, root: str) -> list[dict]:
    base = f"{root}/skins"
    if not await device.exists(base):
        return []
    found: list[dict] = []
    for name in await device.ls(base):
        path = f"{base}/{name}"
        try:
            stat = await device.stat(path)
        except Exception:
            continue
        if stat.get("st_ifmt") != "S_IFDIR":
            continue
        try:
            files = await device.ls(path)
        except Exception:
            files = []
        cards = [f for f in files
                 if f.lower().startswith("ut_handcard_") and f.lower().endswith(".png")]
        found.append({"name": name, "path": path, "files": len(files), "cards": len(cards)})
    return sorted(found, key=lambda item: item["name"].lower())


async def skins_import(device: Device, root: str, zip_path: str | Path,
                       scheme: str | None = None) -> dict:
    """导入一个卡面方案包：包内应只有一个目录，里面是 UT_HandCard_*.png。"""
    import zipfile

    archive_path = Path(zip_path)
    if not archive_path.is_file():
        raise RuntimeError(f"找不到 ZIP：{archive_path}")
    if archive_path.stat().st_size > 512 * 1024 * 1024:
        raise RuntimeError("ZIP 超过 512 MB")

    with zipfile.ZipFile(archive_path) as archive:
        names = zip_members(archive)
        if len(names) > 20000:
            raise RuntimeError(f"条目太多（{len(names)}）")
        cards = [n for n in names if Path(n).name.lower().startswith("ut_handcard_")]
        if not cards:
            raise RuntimeError("包里没有 UT_HandCard_*.png，看起来不是卡面方案")
        roots = sorted({n.split("/")[0] for n in names if "/" in n})
        if len(roots) != 1:
            raise RuntimeError("包内应当只有一个方案目录")
        folder = roots[0]
        name = scheme or folder
        if not SKIN_NAME_RE.fullmatch(name):
            raise RuntimeError("方案名只能用字母数字、下划线和短横线（≤32）")

        stage = WORK_DIR / "skins" / name
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        written = 0
        for member in names:
            parts = member.split("/")
            if parts[0] != folder or len(parts) < 2:
                continue
            target = stage.joinpath(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target, "wb") as destination:
                shutil.copyfileobj(source, destination)
            written += 1

    skins_dir = f"{root}/skins"
    await device.makedirs(skins_dir)
    if await device.exists(f"{skins_dir}/{name}"):
        await device.rm(f"{skins_dir}/{name}")
    await device.push(stage, skins_dir)
    if not await device.exists(f"{skins_dir}/{name}"):
        raise RuntimeError("推送后回读不到方案目录")
    return {"name": name, "cards": len(cards), "files": written,
            "path": f"{skins_dir}/{name}"}


async def skins_activate(device: Device, root: str, name: str) -> dict:
    """把方案名写进 CardSkinMod 的 config.json 的 ActiveSkin（文本定点替换，保留注释）。"""
    if not SKIN_NAME_RE.fullmatch(name):
        raise RuntimeError("非法方案名")
    for folder in ("mods", "disabled_mods"):
        config = f"{root}/{folder}/{SKIN_MOD_ID}/config.json"
        if not await device.exists(config):
            continue
        text = (await device.read(config)).decode("utf-8-sig", "replace")
        pattern = re.compile(r'("ActiveSkin"\s*:\s*)"(?:[^"\\]|\\.)*"')
        if not pattern.search(text):
            raise RuntimeError('配置里没有 "ActiveSkin" 项')
        updated = pattern.sub(lambda match: match.group(1) + json.dumps(name, ensure_ascii=False),
                              text, count=1)
        await device.write(config, updated.encode("utf-8"))
        check = (await device.read(config)).decode("utf-8-sig", "replace")
        if not pattern.search(check):
            raise RuntimeError("回读失败")
        return {"id": SKIN_MOD_ID, "path": config, "active": name,
                "enabled": folder == "mods"}
    raise RuntimeError(f"找不到 {SKIN_MOD_ID} 的配置（模组未安装？）")
