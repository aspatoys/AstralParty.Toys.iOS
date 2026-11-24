"""载荷投放 —— 整理载荷目录并推到容器。"""

from __future__ import annotations

from pathlib import Path
import os
import shutil

from .device import Device
from .output import log
from .paths import LOADER_DIR, ROOT, WORK_DIR

PAYLOAD_SKIP_DIRS = {"licenses", "license"}


PAYLOAD_SKIP_SUFFIXES = {".pdb", ".txt", ".md", ".xml", ".lib", ".exp", ".iobj", ".ipdb"}

# 载荷里的 SDK 位置；iOS 上没有 user32/winmm，SDK 必须能退回 Unity 后端
SDK_RELATIVE = "sdk/CesiumLoader.SDK.dll"
# 能力标记：加载器构造原生后端失败时会调 MobilePlatform.MarkNativeUnavailable 退回 Unity
# 后端；只有带这个符号的构建才能在 iOS 上活着（只认平台的旧构建会漏判 iOS）。
CAPABLE_MARKERS = (b"MarkNativeUnavailable",)
ALLOW_DESKTOP_ENV = "CESIUM_ALLOW_DESKTOP_SDK"


def sdk_bytes_ios_capable(data: bytes) -> bool:
    """这份 SDK 能不能在没有 user32 的平台上用（没有原生后端时会不会退回 Unity）。"""
    return any(marker in data for marker in CAPABLE_MARKERS)


def sdk_ios_capable(root: Path) -> bool | None:
    """载荷里的 SDK 能不能在 iOS 上用；没有 SDK 时返回 None（不表态）。"""
    sdk = Path(root) / SDK_RELATIVE
    if not sdk.is_file():
        return None
    return sdk_bytes_ios_capable(sdk.read_bytes())


def assert_sdk_usable(root: Path) -> None:
    """投放前挡住跑不起来的 SDK —— 装上去会让热键模组每帧抛异常、把游戏卡死。"""
    if os.environ.get(ALLOW_DESKTOP_ENV):
        return
    if sdk_ios_capable(Path(root)) is False:
        raise RuntimeError(
            f"{SDK_RELATIVE} 没有「原生后端不可用时退回 Unity」的兜底（不含 "
            "MobilePlatform.MarkNativeUnavailable）—— iOS 上热键模组会每帧抛 "
            "DllNotFoundException(user32.dll)，游戏会卡在大厅/对局里。"
            "请换一份新版加载器的移动端构建 SDK 再投放；确认要装原样文件时设 "
            f"{ALLOW_DESKTOP_ENV}=1。")


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
    投上去只是拖长安装时间，这里直接跳过。投放前会先确认 SDK 是移动端构建。
    """
    assert_sdk_usable(payload)
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
