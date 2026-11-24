"""宿主配置 —— 路径、版本号、市场地址与超时。"""

from __future__ import annotations

from pathlib import Path

import cesium_ios as engine

PACKAGE_DIR = Path(__file__).resolve().parent    # iOS/host

HERE = PACKAGE_DIR.parent                        # iOS/：界面源码与载荷都相对它定位

WEBUI = HERE / "webui"

DIST = WEBUI / "dist"

LOADER_ROOT = f"/Documents/{engine.LOADER_DIR}"

APP_VERSION = "0.3.0"

MARKET_BASE = "https://forge.hiynet.com"

CONSENT_VERSION = 2

HTTP_TIMEOUT = 12.0

DOWNLOAD_LIMIT = 512 * 1024 * 1024
