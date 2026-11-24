"""市场 HTTP —— 市场列表/详情/下载与包结构识别（不走页面 fetch，因此没有跨域问题）。"""

from __future__ import annotations

from pathlib import Path
import cesium_ios as engine
import json
import shutil
import urllib.parse
import urllib.request
import zipfile

from .config import APP_VERSION, DOWNLOAD_LIMIT, HTTP_TIMEOUT

def _http_json(url: str, timeout: float = HTTP_TIMEOUT) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": f"AstralParty.Toys.iOS/{APP_VERSION}", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(8 * 1024 * 1024)
    return json.loads(raw.decode("utf-8"))


def _http_download(url: str, target: Path, timeout: float = 60.0) -> int:
    request = urllib.request.Request(
        url, headers={"User-Agent": f"AstralParty.Toys.iOS/{APP_VERSION}"})
    total = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response, open(target, "wb") as sink:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > DOWNLOAD_LIMIT:
                raise RuntimeError("下载超过 512 MB")
            sink.write(chunk)
    return total


def _absolute(base: str, value: str | None) -> str | None:
    """市场返回的 coverUrl / downloadUrl 是相对路径（/api/...），补成绝对地址。

    页面是 http://127.0.0.1:<port>，相对路径会被当成页面自己的地址，封面就全 404 了。
    """
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/"):
        return base + value
    return f"{base}/{value}"


def _locate_mod_root(archive_path: Path, mod_id: str) -> Path:
    """解开市场包并找到真正的模组目录（含 <目录名>.dll 的那一层）。"""
    stage = engine.WORK_DIR / "market" / "extract" / mod_id
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    with zipfile.ZipFile(archive_path) as archive:
        names = engine._zip_members(archive)
        if len(names) > 20000:
            raise RuntimeError("包内条目过多")
        for member in names:
            parts = member.split("/")
            if parts[0] in ("mods", "AstralParty_ModLoader") and len(parts) > 1:
                parts = parts[1:]
            target = stage.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink)

    for candidate in [stage, *[p for p in stage.iterdir() if p.is_dir()]]:
        if (candidate / f"{candidate.name}.dll").is_file():
            return candidate
    for dll in stage.rglob("*.dll"):
        if dll.with_suffix(".json").is_file():
            return dll.parent
    raise RuntimeError("无法识别的包结构（找不到 <ModId>/<ModId>.dll）")
