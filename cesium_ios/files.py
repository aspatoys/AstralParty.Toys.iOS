"""文件管理 —— 设备侧文件浏览与增删改移（复制粘贴、上传下载、双击打开）。"""

from __future__ import annotations

from pathlib import Path
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

from .common import stamp
from .device import Device
from .paths import WORK_DIR

FS_ROOT = "/Documents"


FS_CONFLICTS = ("rename", "overwrite", "skip")


OPEN_DIR = Path(tempfile.gettempdir()) / "cesium-ios-open"


def fs_guard(path: str) -> str:
    """规范化设备路径并限制在 /Documents 内（拒绝 ..、反斜杠、空路径）。"""
    raw = str(path or "").strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        raise RuntimeError("非法的设备路径")
    parts: list[str] = []
    for segment in raw.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise RuntimeError("路径里不能包含 ..")
        parts.append(segment)
    if not parts or parts[0] != "Documents":
        raise RuntimeError("只能在 /Documents 下操作")
    return "/" + "/".join(parts)


def fs_join(base: str, name: str) -> str:
    """把 base 与一层名字拼起来，拒绝带分隔符的非法名字。"""
    visible = str(name or "").strip()
    if not visible or visible in (".", "..") or any(ch in visible for ch in "/\\\x00:"):
        raise RuntimeError(f"非法的名称：{name}")
    return f"{fs_guard(base).rstrip('/')}/{visible}"


def fs_conflict(value: str | None) -> str:
    policy = str(value or "rename").lower()
    return policy if policy in FS_CONFLICTS else "rename"


def _ext_split(name: str) -> tuple[str, str]:
    """`x.txt` → (`x`, `.txt`)；没有像样后缀就当没有后缀。"""
    stem, dot, ext = name.rpartition(".")
    if dot and stem and len(ext) <= 8:
        return stem, "." + ext
    return name, ""


async def fs_unique_name(device: Device, base: str, name: str, is_dir: bool) -> str:
    """在 base 下找一个不冲突的名字：`x.txt` → `x (1).txt`。"""
    existing = {item.lower() for item in await device.ls(base)}
    if name.lower() not in existing:
        return name
    stem, ext = (name, "") if is_dir else _ext_split(name)
    for index in range(1, 1000):
        candidate = f"{stem} ({index}){ext}"
        if candidate.lower() not in existing:
            return candidate
    raise RuntimeError(f"{name} 的重名副本太多")


def unique_local(target: Path, name: str, is_dir: bool) -> Path:
    """本地侧同样的重名规则（下载到设备外部时用）。"""
    candidate = target / name
    if not candidate.exists():
        return candidate
    stem, ext = (name, "") if is_dir else _ext_split(name)
    for index in range(1, 1000):
        attempt = target / f"{stem} ({index}){ext}"
        if not attempt.exists():
            return attempt
    raise RuntimeError(f"{name} 的重名副本太多")


async def _plan_target(device: Device, base: str, name: str, is_dir: bool,
                       conflict: str) -> str | None:
    """按冲突策略给出最终名字；skip 时返回 None。"""
    existing = {item.lower() for item in await device.ls(base)}
    if name.lower() not in existing:
        return name
    if conflict == "skip":
        return None
    if conflict == "overwrite":
        await device.rm(f"{base.rstrip('/')}/{name}", force=True)
        return name
    return await fs_unique_name(device, base, name, is_dir)


def _inside(child: str, parent: str) -> bool:
    """child 是否就是 parent 或位于 parent 之下。"""
    child, parent = child.rstrip("/"), parent.rstrip("/")
    return child == parent or child.startswith(parent + "/")


def _name_of(path: str) -> str:
    return path.rstrip("/").rsplit("/", 1)[-1]


FS_STAT_CONCURRENCY = 24


async def _describe(device: Device, base: str, name: str) -> dict:
    """一个条目的元信息；stat 失败也照样列出来（权限之类的只影响属性）。"""
    full = f"{base.rstrip('/')}/{name}"
    item = {"name": name, "path": full, "dir": False, "bytes": None, "mtime": ""}
    try:
        stat = await device.stat(full)
        item["dir"] = stat.get("st_ifmt") == "S_IFDIR"
        item["bytes"] = stat.get("st_size")
        item["mtime"] = stamp(stat.get("st_mtime"))
    except Exception:
        pass
    return item


async def fs_list(device: Device, path: str, show_hidden: bool = False) -> list[dict]:
    """列一层目录。目录排在文件前面，各自按名字排序。

    设备上的 AFC READ_DIR 只回文件名（不带 st_size / st_ifmt / st_mtime，实测 iOS 18），
    所以大小与时间只能逐个 stat。一次 stat 约 1 ms，几千个文件顺着他走就是好几秒；AFC 用
    packet_num 配对响应、支持流水线，因此这里并发发出去，实测 24 路并发能快一个数量级。
    """
    names = [name for name in await device.ls(path) if show_hidden or not name.startswith(".")]
    semaphore = asyncio.Semaphore(FS_STAT_CONCURRENCY)

    async def one(name: str) -> dict:
        async with semaphore:
            return await _describe(device, path, name)

    entries = list(await asyncio.gather(*(one(name) for name in names)))
    entries.sort(key=lambda entry: (not entry["dir"], entry["name"].lower()))
    return entries


async def fs_read(device: Device, path: str, max_bytes: int = 256 * 1024) -> dict:
    """读文件做预览；二进制或超限只回元信息。"""
    if not await device.exists(path):
        raise RuntimeError("文件不存在")
    stat = await device.stat(path)
    if stat.get("st_ifmt") == "S_IFDIR":
        raise RuntimeError("这是一个目录")
    size = int(stat.get("st_size") or 0)
    if size > max_bytes:
        return {"path": path, "bytes": size, "binary": None, "truncated": True,
                "text": None, "note": f"超过预览上限 {max_bytes} B"}
    data = await device.read(path)
    binary = b"\x00" in data[:8192]
    return {"path": path, "bytes": len(data), "binary": binary, "truncated": False,
            "text": None if binary else data.decode("utf-8", "replace")}


async def fs_mkdir(device: Device, base: str, name: str) -> dict:
    target = fs_join(base, name)
    if await device.exists(target):
        raise RuntimeError(f"{name} 已存在")
    await device.makedirs(target)
    return {"path": target}


async def fs_rename(device: Device, path: str, name: str) -> dict:
    source = fs_guard(path)
    if source == FS_ROOT:
        raise RuntimeError("不能重命名 /Documents")
    target = fs_join(source.rsplit("/", 1)[0], name)
    if target == source:
        return {"path": source}
    if await device.exists(target):
        raise RuntimeError(f"{name} 已存在")
    await device.rename(source, target)
    return {"path": target}


async def fs_delete(device: Device, paths: list[str]) -> dict:
    deleted: list[str] = []
    failed: list[dict] = []
    for raw in paths:
        try:
            path = fs_guard(raw)
        except Exception as error:  # noqa: BLE001
            failed.append({"path": str(raw), "error": str(error)})
            continue
        if path == FS_ROOT:
            failed.append({"path": path, "error": "不能删除 /Documents"})
            continue
        try:
            left = await device.rm(path, force=True)
            if left:
                failed.append({"path": path, "error": "部分内容没能删除"})
            else:
                deleted.append(path)
        except Exception as error:  # noqa: BLE001
            failed.append({"path": path, "error": str(error)})
    return {"deleted": deleted, "failed": failed}


async def fs_move(device: Device, sources: list[str], target: str,
                  conflict: str = "rename") -> dict:
    """同卷移动：AFC rename，不经过本地中转。"""
    base = fs_guard(target)
    policy = fs_conflict(conflict)
    moved: list[str] = []
    skipped: list[str] = []
    failed: list[dict] = []
    for raw in sources:
        try:
            source = fs_guard(raw)
            if source == FS_ROOT:
                raise RuntimeError("不能移动 /Documents")
            name = _name_of(source)
            if source.rsplit("/", 1)[0] == base:
                skipped.append(source)          # 已经在目标目录里
                continue
            is_dir = await device.isdir(source)
            if is_dir and _inside(base, source):
                raise RuntimeError("不能把目录移进它自己")
            final = await _plan_target(device, base, name, is_dir, policy)
            if final is None:
                skipped.append(source)
                continue
            await device.rename(source, f"{base.rstrip('/')}/{final}")
            moved.append(f"{base.rstrip('/')}/{final}")
        except Exception as error:  # noqa: BLE001
            failed.append({"path": str(raw), "error": str(error)})
    return {"moved": moved, "skipped": skipped, "failed": failed}


async def _pull_item(device: Device, source: str, is_dir: bool, stage: Path) -> Path:
    """把设备上的一项拉到本地暂存目录，返回本地路径。"""
    name = _name_of(source)
    if is_dir:
        await device.pull(source, stage)
        return stage / name
    local = stage / name
    await device.pull(source, local)
    return local


async def fs_copy(device: Device, sources: list[str], target: str,
                  conflict: str = "rename") -> dict:
    """复制 = 拉回本地暂存再推上去（AFC 没有服务端复制）。"""
    base = fs_guard(target)
    policy = fs_conflict(conflict)
    stage = WORK_DIR / "fs" / uuid.uuid4().hex
    copied: list[str] = []
    skipped: list[str] = []
    failed: list[dict] = []
    try:
        for raw in sources:
            try:
                source = fs_guard(raw)
                if source == FS_ROOT:
                    raise RuntimeError("不能复制 /Documents")
                is_dir = await device.isdir(source)
                if _inside(base, source):
                    raise RuntimeError("不能把目录复制进它自己")
                name = _name_of(source)
                final = await _plan_target(device, base, name, is_dir, policy)
                if final is None:
                    skipped.append(source)
                    continue
                local = await _pull_item(device, source, is_dir, stage)
                if final != name:
                    local = local.rename(local.with_name(final))
                await device.push(local, base)
                copied.append(f"{base.rstrip('/')}/{final}")
            except Exception as error:  # noqa: BLE001
                failed.append({"path": str(raw), "error": str(error)})
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"copied": copied, "skipped": skipped, "failed": failed}


async def fs_upload(device: Device, local_paths: list[str], target: str,
                    conflict: str = "overwrite") -> dict:
    """本地 → 设备。目录改名时先在本地暂存目录里改名再推。"""
    base = fs_guard(target)
    policy = fs_conflict(conflict)
    stage = WORK_DIR / "fs" / uuid.uuid4().hex
    uploaded: list[str] = []
    skipped: list[str] = []
    failed: list[dict] = []
    try:
        for raw in local_paths:
            try:
                local = Path(str(raw)).expanduser()
                if not local.exists():
                    raise RuntimeError("本地路径不存在")
                name = local.name
                final = name
                existing = {item.lower() for item in await device.ls(base)}
                if name.lower() in existing:
                    if policy == "skip":
                        skipped.append(name)
                        continue
                    if policy == "overwrite":
                        await device.rm(f"{base.rstrip('/')}/{name}", force=True)
                    else:
                        final = await fs_unique_name(device, base, name, local.is_dir())
                if final != name:
                    stage.mkdir(parents=True, exist_ok=True)
                    staged = stage / final
                    if staged.exists():
                        if staged.is_dir():
                            shutil.rmtree(staged, ignore_errors=True)
                        else:
                            staged.unlink()
                    if local.is_dir():
                        shutil.copytree(local, staged)
                    else:
                        shutil.copy2(local, staged)
                    local = staged
                await device.push(local, base)
                uploaded.append(f"{base.rstrip('/')}/{final}")
            except Exception as error:  # noqa: BLE001
                failed.append({"path": str(raw), "error": str(error)})
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"uploaded": uploaded, "skipped": skipped, "failed": failed}


async def fs_download(device: Device, sources: list[str], local_dir: str) -> dict:
    """设备 → 本地目录；重名自动加 `(1)`。"""
    dest = Path(str(local_dir)).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    failed: list[dict] = []
    for raw in sources:
        try:
            source = fs_guard(raw)
            name = _name_of(source)
            if await device.isdir(source):
                # 先拉到本地的临时目录，再按重名规则搬进目标目录，
                # 否则重名时 pull 会并进同名目录里，把用户原有的东西搞混
                scratch = dest / f".cesium-pull-{uuid.uuid4().hex}"
                scratch.mkdir(parents=True, exist_ok=True)
                try:
                    await device.pull(source, scratch)
                    target = unique_local(dest, name, True)
                    shutil.move(str(scratch / name), str(target))
                finally:
                    shutil.rmtree(scratch, ignore_errors=True)
                saved.append(str(target))
            else:
                target = unique_local(dest, name, False)
                await device.pull(source, target)
                saved.append(str(target))
        except Exception as error:  # noqa: BLE001
            failed.append({"path": str(raw), "error": str(error)})
    return {"saved": saved, "failed": failed}


def open_with_default(local: Path) -> None:
    """用系统默认程序打开本地文件/目录。"""
    if sys.platform == "win32":
        os.startfile(str(local))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(local)])
    else:
        subprocess.Popen(["xdg-open", str(local)])


async def fs_download_open(device: Device, path: str) -> dict:
    """双击打开：先拉到临时目录，再交给系统默认程序。"""
    source = fs_guard(path)
    name = _name_of(source)
    is_dir = await device.isdir(source)
    OPEN_DIR.mkdir(parents=True, exist_ok=True)
    local = OPEN_DIR / name
    if local.exists():
        # 上次打开的副本可能还被别的程序占着，删不掉就换个名字
        try:
            shutil.rmtree(local) if local.is_dir() else local.unlink()
        except OSError:
            local = unique_local(OPEN_DIR, name, is_dir)
    if is_dir:
        await device.pull(source, OPEN_DIR)
        local = OPEN_DIR / name
    else:
        await device.pull(source, local)
    open_with_default(local)
    return {"path": source, "local": str(local)}
