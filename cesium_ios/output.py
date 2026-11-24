"""输出 —— 所有打印都过这一层：既能被 GUI 接管，也会落到本机 `logs/`。

日志文件按「一次运行一个文件」写：`logs/<前缀>-<yyyyMMdd-HHmmss>.log`，每行前面带
`HH:MM:SS` 时间戳，只保留最近 `LOG_KEEP` 份（和加载器那边的口径一致）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from .paths import ROOT

_OUTPUT_HOOK = None
LOG_KEEP = 20
LOG_DIRNAME = "logs"

_prefix = "run"
_log_path: Path | None = None
_log_failed = False


def set_output_hook(hook) -> None:
    """把输出接给 GUI（传 None 恢复打印到 stdout）。"""
    global _OUTPUT_HOOK
    _OUTPUT_HOOK = hook


def log_dir() -> Path:
    return ROOT / LOG_DIRNAME


def set_log_prefix(prefix: str) -> None:
    """给本次运行定个前缀（`gui` / `cli`），要在第一条输出之前调用。"""
    global _prefix, _log_path
    _prefix = prefix or "run"
    _log_path = None


def log_path() -> Path | None:
    """当前这次运行的日志文件；写不进去的时候返回 None。"""
    global _log_path, _log_failed
    if _log_path is not None or _log_failed:
        return _log_path
    try:
        folder = log_dir()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = folder / f"{_prefix}-{stamp}.log"
        target.write_text("", encoding="utf-8")  # 先建出来，占住这个名字
        _log_path = target
        _prune(folder)
    except Exception:
        _log_failed = True  # 只读目录之类：日志写不了不该影响工具本身
    return _log_path


def _prune(folder: Path, keep: int = LOG_KEEP) -> None:
    """只留最近的 keep 份（按名字里的时间戳排）。"""
    try:
        files = sorted(folder.glob("*.log"), key=lambda item: item.name, reverse=True)
        for stale in files[keep:]:
            try:
                stale.unlink()
            except OSError:
                pass
    except Exception:
        pass


def _write_file(text: str) -> None:
    target = log_path()
    if target is None:
        return
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().strftime('%H:%M:%S')} {text}\n")
    except Exception:
        pass


def log(message: str = "") -> None:
    text = str(message)
    _write_file(text)
    if _OUTPUT_HOOK is not None:
        try:
            _OUTPUT_HOOK(text)
            return
        except Exception:
            pass
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        # 控制台代码页接不住就退到可替换，别让一行中文把整个命令打断
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(encoding, "replace").decode(encoding, "replace"), flush=True)


def ok(message: str) -> None:
    log(f"  [ok]   {message}")


def warn(message: str) -> None:
    log(f"  [warn] {message}")


def bad(message: str) -> None:
    log(f"  [FAIL] {message}")


def section(title: str) -> None:
    log(f"\n=== {title} ===")
