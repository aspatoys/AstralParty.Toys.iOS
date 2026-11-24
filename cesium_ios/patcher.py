"""注入器 —— 编译并调用 CesiumIosPatcher、UnityFS 资产读写。"""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

from .common import decode_output
from .output import log
from .paths import BOOT_DLL, BOOT_METHOD, BOOT_TYPE, LOADER_DIR, TOOLS


def patcher_path() -> Path:
    name = "cesium-ios-patcher.exe" if os.name == "nt" else "cesium-ios-patcher"
    return TOOLS / "CesiumIosPatcher" / "bin" / "Release" / "net8.0" / name


def _sources_newer_than(project: Path, exe: Path) -> bool:
    """源码是否比 exe 新（改了 Program.cs 就得重编，否则跑的还是旧注入逻辑）。"""
    if not exe.exists():
        return True
    newest = exe.stat().st_mtime
    for path in project.rglob("*"):
        if path.suffix not in (".cs", ".csproj"):
            continue
        if {"obj", "bin"} & set(path.relative_to(project).parts):
            continue  # 构建中间产物不算源码
        if path.stat().st_mtime > newest:
            return True
    return False


def ensure_patcher() -> Path:
    exe = patcher_path()
    project = TOOLS / "CesiumIosPatcher"
    if not _sources_newer_than(project, exe):
        return exe
    log("  注入器未编译或源码有更新，正在构建（需要 .NET 8 SDK）…")
    result = subprocess.run(["dotnet", "build", "-c", "Release", "--nologo", "-v", "m"],
                            cwd=project, capture_output=True)
    output = decode_output(result.stdout) + decode_output(result.stderr)
    if result.returncode != 0 or not exe.exists():
        raise RuntimeError("注入器构建失败：\n" + output)
    return exe


def run_patcher(exe: Path, dll_in: Path, dll_out: Path, refs: Path) -> str:
    result = subprocess.run(
        [str(exe), "bootstrap", str(dll_in), str(dll_out),
         "--dir", LOADER_DIR, "--boot-dll", BOOT_DLL,
         "--boot-type", BOOT_TYPE, "--boot-method", BOOT_METHOD, "--boot-arg", "root",
         "--refs", str(refs)],
        capture_output=True)
    output = decode_output(result.stdout) + decode_output(result.stderr)
    if result.returncode != 0:
        raise RuntimeError("注入失败：\n" + output)
    return output


def _import_bundle_tool():
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import bundle_assets  # noqa: E402
    return bundle_assets


def extract_assets(bundle: Path, outdir: Path) -> dict[str, bytes]:
    tool = _import_bundle_tool()
    outdir.mkdir(parents=True, exist_ok=True)
    items = tool.read_all(str(bundle))
    for name, data in items.items():
        (outdir / name).write_bytes(data)
    return items


def replace_asset(bundle: Path, asset: str, new_file: Path, out_bundle: Path) -> None:
    tool = _import_bundle_tool()
    out_bundle.parent.mkdir(parents=True, exist_ok=True)
    code = tool.cmd_replace(str(bundle), asset, str(new_file), str(out_bundle))
    if code != 0:
        raise RuntimeError("bundle 换回失败")
