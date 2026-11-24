"""市场页宿主方法 —— 免责声明、列表、详情、按版本安装。"""

from __future__ import annotations

import cesium_ios as engine
import re
import urllib.parse

from .config import CONSENT_VERSION, LOADER_ROOT, MARKET_BASE
from .market import _absolute, _http_download, _http_json, _locate_mod_root

class MarketApi:
    """免责声明、列表、详情、按版本安装。"""

    def _market(self) -> dict:
        state = engine.load_state()
        return dict(state.get("market") or {})


    def _market_write(self, **changes) -> dict:
        state = engine.load_state()
        market = state.setdefault("market", {})
        market.update(changes)
        engine.save_state(state)
        return self.market_state()


    def market_state(self) -> dict:
        market = self._market()
        return {
            "baseUrl": market.get("baseUrl") or MARKET_BASE,
            "consentVersion": int(market.get("consentVersion") or 0),
            "requiredVersion": CONSENT_VERSION,
            "accepted": int(market.get("consentVersion") or 0) >= CONSENT_VERSION,
        }


    def market_consent(self, accepted: bool) -> dict:
        """同意/撤回免责声明。未同意时不会有任何请求打到市场。"""
        return self._market_write(consentVersion=CONSENT_VERSION if accepted else 0)


    def set_market_base(self, url: str) -> dict:
        url = (url or "").strip().rstrip("/")
        if url and not re.match(r"^https?://", url):
            return {"error": "地址必须以 http:// 或 https:// 开头"}
        return {"ok": True, **self._market_write(baseUrl=url or MARKET_BASE)}


    def _require_consent(self) -> None:
        if not self.market_state()["accepted"]:
            raise RuntimeError("未同意免责声明，不会连接市场服务")


    def market_list(self, page: int = 1, lang: str = "zh-Hans") -> dict:
        try:
            self._require_consent()
            base = self.market_state()["baseUrl"].rstrip("/")
            query = urllib.parse.urlencode({"page": int(page), "lang": lang})
            data = _http_json(f"{base}/api/mods?{query}")
            items = data.get("items") or []
            for item in items:
                item["coverUrl"] = _absolute(base, item.get("coverUrl"))
                item["downloadUrl"] = _absolute(base, item.get("downloadUrl"))
            return {"ok": True, "total": data.get("total"), "page": data.get("page"),
                    "pageSize": data.get("pageSize"), "tags": data.get("tags") or [],
                    "items": items}
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "error": str(error)}


    def market_detail(self, mod_id: str, lang: str = "zh-Hans") -> dict:
        try:
            self._require_consent()
            base = self.market_state()["baseUrl"].rstrip("/")
            query = urllib.parse.urlencode({"lang": lang})
            detail = _http_json(f"{base}/api/mods/{urllib.parse.quote(mod_id)}?{query}")
            detail["coverUrl"] = _absolute(base, detail.get("coverUrl"))
            for version in detail.get("versions") or []:
                version["downloadUrl"] = _absolute(base, version.get("downloadUrl"))
            return {"ok": True, "detail": detail}
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "error": str(error)}


    def market_install(self, mod_id: str, version: str | None = None,
                       lang: str = "zh-Hans") -> dict:
        async def work():
            self._require_consent()
            base = self.market_state()["baseUrl"].rstrip("/")
            query = urllib.parse.urlencode({"lang": lang})
            detail = _http_json(f"{base}/api/mods/{urllib.parse.quote(mod_id)}?{query}")
            versions = detail.get("versions") or []
            if not versions:
                raise RuntimeError("该模组没有可下载版本")
            target = next((item for item in versions if item.get("version") == version), None)
            target = target or versions[0]
            url = target.get("downloadUrl") or ""
            if not url:
                raise RuntimeError("这个版本没有下载地址")
            if url.startswith("/"):
                url = base + url

            engine.section("安装市场模组")
            engine.log(f"  {mod_id} {target.get('version') or 'latest'}")
            archive = engine.WORK_DIR / "market" / f"{mod_id}-{target.get('version') or 'latest'}.zip"
            size = _http_download(url, archive)
            actual = engine.sha256_file(archive)
            expect = (target.get("sha256") or "").lower()
            engine.ok(f"已下载 {size} B  {actual[:16]}…")
            if expect and expect != actual:
                raise RuntimeError(f"SHA-256 不匹配：{actual} != {expect}")

            root = _locate_mod_root(archive, mod_id)
            engine.ok(f"包结构识别为 {root.name}")

            await self._release()

            async def push(device):
                mods_dir = f"{LOADER_ROOT}/mods"
                await device.makedirs(mods_dir)
                target_dir = f"{mods_dir}/{root.name}"
                if await device.exists(target_dir):
                    await device.rm(target_dir)
                await device.push(root, mods_dir)
                self._mods = await engine.mod_inventory(device, LOADER_ROOT)
                return {"id": root.name}

            return await self._with_device(push)

        def after(_result) -> None:
            self._report = None

        return self._spawn(f"安装 {mod_id}", work(), after=after)
