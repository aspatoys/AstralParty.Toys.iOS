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


# 移动端库改名后的目标命名（3.9.0 起）：写入一律用新名。
BOOT_DLL = "CesiumLoader.Mobile.Bootstrap.dll"


BOOT_TYPE = "CesiumLoader.Mobile.Bootstrap.Boot"


BOOT_METHOD = "LoadForGame"


API_DLL = "CesiumLoader.Mobile.API.dll"


# 双名兼容读：读路径同时接受旧名，写路径只写新名。引导目录里旧名还在时提示「需重装」。
LEGACY_BOOT_DLL = "CesiumLoader.Android.Bootstrap.dll"


LEGACY_BOOT_TYPE = "CesiumLoader.Android.Bootstrap.Boot"


LEGACY_API_DLL = "CesiumAndroidApi.dll"


# 上面这份旧名是补丁判定的关键：旧补丁里烧的是旧类型名的 ldstr 字面量，
# 只认到旧名时必须判成「已过期，需重新注入」，绝不能判成「已注入」（否则新载荷配旧补丁，
# 引导加载会停在 cesium_ios_s3_read 之后）。
BOOT_DLLS = (BOOT_DLL, LEGACY_BOOT_DLL)


API_DLLS = (API_DLL, LEGACY_API_DLL)


# 补丁标记是类型名的字节形式：ldstr 字面量落在 #US 堆里是 UTF-16，
# 类型名在 #Strings 堆里则可能是 ASCII（UTF-8）形式，两种都认。
PATCH_MARKER = BOOT_TYPE.encode()


PATCH_MARKER_UTF16 = BOOT_TYPE.encode("utf-16-le")


LEGACY_PATCH_MARKER = LEGACY_BOOT_TYPE.encode()


LEGACY_PATCH_MARKER_UTF16 = LEGACY_BOOT_TYPE.encode("utf-16-le")


def patch_with_current_type(data: bytes) -> bool:
    """程序集里烧的是**新**引导类型名 —— 这份补丁现在仍然有效。"""
    return PATCH_MARKER in data or PATCH_MARKER_UTF16 in data


def patch_with_legacy_type(data: bytes) -> bool:
    """程序集里只有**旧**引导类型名 —— 旧补丁，必须重新注入。

    已经带新类型名的补丁一律算「当前」，即使其它地方的旧类型名字符串还在（改名前的
    程序集元数据里就可能残留），也只有「只认到旧名」才是真正需要重新注入的情况。
    """
    if patch_with_current_type(data):
        return False
    return LEGACY_PATCH_MARKER in data or LEGACY_PATCH_MARKER_UTF16 in data


def pick_bootstrap(entries) -> str | None:
    """引导 DLL 的目录清单：谁在就用谁（新名优先，旧名兜底）。"""
    for name in BOOT_DLLS:
        if name in entries:
            return name
    return None


def pick_api(entries) -> str | None:
    """悬浮窗 API 的目录清单：同样是新名优先。"""
    for name in API_DLLS:
        if name in entries:
            return name
    return None


# 见过/可能的包名（国服 iOS 是 com.feimo.astralpartycn，与安卓不同）
CANDIDATE_IDS = (
    "com.feimo.astralpartycn",
    "com.feimo.astralparty",
    "com.feimo.jxpd",
    "com.feimo.astralparty.cesium",
)
