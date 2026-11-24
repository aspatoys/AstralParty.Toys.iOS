"""通用工具 —— state.json 读写、哈希、时间戳、子进程输出解码、ZIP 条目校验。"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import locale
import re

from .paths import STATE_PATH


def decode_output(raw: bytes | None) -> str:
    """解码子进程的输出。

    .NET / 原生程序往**管道**里写字时用的是系统 ANSI 代码页（中文 Windows 上是 GBK），
    不是 UTF-8；直接按 UTF-8 解就会把「注入」这类中文变成乱码。这里先按 UTF-8 严格解，
    解不开再退回本机代码页 —— 谁写的就用谁的解码。
    """
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode(locale.getpreferredencoding(False), "replace")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def stamp(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value or "")


def zip_members(archive) -> list[str]:
    names: list[str] = []
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if name.endswith("/"):
            continue
        parts = name.split("/")
        if name.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", name):
            raise RuntimeError(f"包里含非法路径：{name}")
        names.append(name)
    return names
