"""本机目录与常量 —— 数据目录、容器内布局、包名候选。

`ROOT` 是仓库里的 `iOS/` 目录：`state.json`、`backups/`、`work/`、`payload/` 都在它下面，
整个目录搬走即可换机。`HERE` 是它以前的名字，留给外部脚本。
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent   # iOS/cesium_ios

ROOT = PACKAGE_DIR.parent                       # iOS/：数据目录与本工具同级

HERE = ROOT

TOOLS = ROOT / "tools"

STATE_PATH = ROOT / "state.json"

BACKUP_DIR = ROOT / "backups"

WORK_DIR = ROOT / "work"


ASSET_NAME = "AstralParty.Runtime.dll"


ADDR_REL = "com.unity.addressables"


BUNDLES_REL = ADDR_REL + "/AssetBundles"


LOADER_DIR = "CesiumLoader"


BOOT_DLL = "CesiumLoader.Android.Bootstrap.dll"


BOOT_TYPE = "CesiumLoader.Android.Bootstrap.Boot"


BOOT_METHOD = "LoadForGame"


PATCH_MARKER = BOOT_TYPE.encode()             # #Strings 堆里可能出现 ASCII 形式


PATCH_MARKER_UTF16 = BOOT_TYPE.encode("utf-16-le")  # ldstr 字面量在 #US 堆里是 UTF-16


# 见过/可能的包名（国服 iOS 是 com.feimo.astralpartycn，与安卓不同）
CANDIDATE_IDS = (
    "com.feimo.astralpartycn",
    "com.feimo.astralparty",
    "com.feimo.jxpd",
    "com.feimo.astralparty.cesium",
)
