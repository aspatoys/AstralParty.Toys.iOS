"""设备通道 —— house_arrest 会话、设备/应用发现。"""

from __future__ import annotations

from pathlib import Path
import json
import os
import re
import subprocess
import sys

from .common import decode_output
from .paths import CANDIDATE_IDS

def _house_arrest():
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService
    return create_using_usbmux, HouseArrestService


class Device:
    """`Documents` 子树内的读写（`VendContainer` 对 App Store 应用会被拒）。"""

    def __init__(self, bundle_id: str, service):
        self.bundle_id = bundle_id
        self.svc = service

    async def ls(self, remote: str) -> list[str]:
        return sorted(await self.svc.listdir(remote))

    async def exists(self, remote: str) -> bool:
        return await self.svc.exists(remote)

    async def read(self, remote: str) -> bytes:
        return await self.svc.get_file_contents(remote)

    async def write(self, remote: str, data: bytes) -> None:
        await self.svc.set_file_contents(remote, data)

    async def isdir(self, remote: str) -> bool:
        return await self.svc.isdir(remote)

    async def rm(self, remote: str, force: bool = False) -> list[str]:
        """删除文件或整个目录；force=True 时不抛异常，返回没能删掉的路径。"""
        return await self.svc.rm(remote, force=force)

    async def rename(self, src: str, dst: str) -> None:
        await self.svc.rename(src, dst)

    async def stat(self, remote: str) -> dict:
        return await self.svc.stat(remote)

    async def pull(self, remote: str, local: Path, progress: bool = False) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        await self.svc.pull(remote, str(local), progress_bar=progress)

    async def push(self, local: Path, remote_dir: str, progress: bool = False) -> None:
        await self.svc.push(str(local), remote_dir, progress_bar=progress)

    async def makedirs(self, remote: str) -> None:
        # AfcService.makedirs 只有 filename 一个参数，重复创建会报错，所以先判存在
        if await self.svc.exists(remote):
            return
        await self.svc.makedirs(remote)


class _Session:
    def __init__(self, lockdown, service):
        self.lockdown = lockdown
        self.service = service


async def open_device(bundle_id: str) -> tuple[Device, _Session]:
    create_using_usbmux, HouseArrestService = _house_arrest()
    lockdown = await create_using_usbmux(autopair=True)
    try:
        service = await HouseArrestService.create(lockdown, bundle_id, documents_only=True)
    except Exception:
        await lockdown.close()
        raise
    return Device(bundle_id, service), _Session(lockdown, service)


async def close_device(session: _Session) -> None:
    try:
        await session.service.close()
    finally:
        await session.lockdown.close()


def check_dependencies() -> None:
    """早失败：缺依赖时直接说清楚是哪个解释器缺什么，别一路走到「没找到游戏」。"""
    missing = []
    for module in ("pymobiledevice3", "UnityPy"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        raise RuntimeError(
            "缺少 Python 依赖：" + "、".join(missing) + "\n"
            f"  当前解释器：{sys.executable}\n"
            "  解决：用 `uv run main.py` 跑（会按 pyproject.toml 自动建 .venv 装依赖）；\n"
            "  或者给这个解释器装上：pip install pymobiledevice3 UnityPy==1.25.3 pywebview")


def run_pmd(*args: str) -> tuple[int, str, str]:
    """调用 pymobiledevice3 CLI（只用于设备与应用列表这类一次性查询）。

    子进程强制 UTF-8 输出（Windows 上默认按控制台代码页写，按 UTF-8 解会把中文设备名
    解成乱码）；解码仍走 decode_output，万一子进程没吃到环境变量也不会出乱码。
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    result = subprocess.run([sys.executable, "-m", "pymobiledevice3", *args],
                            capture_output=True, env=env)
    return result.returncode, decode_output(result.stdout), decode_output(result.stderr)


def list_devices() -> list[dict]:
    code, out, err = run_pmd("usbmux", "list")
    if code != 0:
        if "No module named" in err:
            check_dependencies()  # 会抛出说明缺哪个包
        detail = err.strip().splitlines()[-1][:300] if err.strip() else f"退出码 {code}"
        raise RuntimeError("枚举设备失败：" + detail)
    match = re.search(r"\[.*\]", out, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except Exception:
        return []


def app_info(bundle_id: str) -> dict | None:
    code, text, err = run_pmd("apps", "query", bundle_id)
    if code != 0 and "No module named" in err:
        check_dependencies()
    start = text.find("{")
    if start < 0:
        return None
    try:
        data = json.loads(text[start:])
    except Exception:
        return None
    # `apps query` 返回的是 {bundle_id: {...}} 形式
    if isinstance(data, dict) and bundle_id in data and isinstance(data[bundle_id], dict):
        return data[bundle_id]
    return data if isinstance(data, dict) and data.get("CFBundleIdentifier") else None


def find_game() -> tuple[str, dict]:
    devices = list_devices()
    if not devices:
        raise RuntimeError("没有检测到 iOS 设备。请用 USB 连接，并在设备上点「信任此电脑」。\n"
                           "  Windows 上还需要 Apple Mobile Device Service 在运行（装了 iTunes 即有）。")
    for bundle_id in CANDIDATE_IDS:
        info = app_info(bundle_id)
        if info:
            return bundle_id, info
    raise RuntimeError("设备上没有找到游戏。已尝试包名：" + "、".join(CANDIDATE_IDS))


def app_version(info: dict) -> str:
    return str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or "")
