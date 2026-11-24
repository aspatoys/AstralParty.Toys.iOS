"""载荷投放 —— 整理载荷目录并推到容器。"""

from __future__ import annotations

from pathlib import Path
import shutil

from .device import Device
from .output import log
from .paths import LOADER_DIR, ROOT, WORK_DIR

PAYLOAD_SKIP_DIRS = {"licenses", "license"}


PAYLOAD_SKIP_SUFFIXES = {".pdb", ".txt", ".md", ".xml", ".lib", ".exp", ".iobj", ".ipdb"}


def stage_payload(payload: Path) -> tuple[Path, list[str]]:
    """挑出真正要上设备的文件：跳过调试符号、说明文本与许可证目录。"""
    stage = WORK_DIR / "payload" / (payload.name or "payload")
    if stage.exists():
        shutil.rmtree(stage)
    skipped: list[str] = []
    for path in sorted(payload.rglob("*")):
        rel = path.relative_to(payload)
        if any(part.lower() in PAYLOAD_SKIP_DIRS for part in rel.parts[:-1]):
            if path.is_file():
                skipped.append(str(rel))
            continue
        if path.is_file() and path.suffix.lower() in PAYLOAD_SKIP_SUFFIXES:
            skipped.append(str(rel))
            continue
        if path.is_dir():
            continue
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return stage, skipped


async def deploy_payload(device: Device, payload: Path, root: str) -> dict:
    """把载荷里**运行时需要的内容**放进 <root>/。

    调试符号（.pdb）、说明文本（.txt/.md）和 licenses/ 对运行没有任何作用，
    投上去只是拖长安装时间，这里直接跳过。
    """
    staged, skipped = stage_payload(payload)
    if skipped:
        log(f"  跳过 {len(skipped)} 个非运行时文件（调试符号 / 说明 / 许可证）")
    sent = 0
    await device.makedirs(root)
    for child in sorted(staged.iterdir()):
        if child.name.startswith("."):
            continue
        await device.push(child, root)
        sent += 1
    return {"sent": sent, "skipped": len(skipped)}


def resolve_payload(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    default = ROOT / "payload" / LOADER_DIR
    return default if default.is_dir() else None
