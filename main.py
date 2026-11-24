#!/usr/bin/env python3
"""AstralParty.Toys.iOS —— 命令行安装 / 检测工具（入口）。

免越狱实现：游戏的热更代码包（承载 `AstralParty.Runtime.dll` 的 Addressables bundle）
是**运行时下载进 app 自身容器**的数据文件，不在签名过的 `.app` 里，因此可以直接改写。
容器读写走 `com.apple.mobile.house_arrest`（`VendDocuments`），无需越狱、无需解密
IPA、无需重签名。

    uv run main.py                     # 交互式菜单
    uv run main.py detect [--json]
    uv run main.py install --payload <目录>
    uv run main.py restore
    uv run main.py uninstall

功能都在 `cesium_ios/` 包里（设备通道、容器内读写、各页面用的流程），这个文件只负责
命令行的入口与老用法的再导出；图形界面见 `gui.py` + `host/`。

依赖声明在 `pyproject.toml`，`uv run` 首次执行会自动建好 `.venv` 并装齐。还需要
.NET 8 SDK —— 首次运行会自动编译 `tools/CesiumIosPatcher` 注入器。
"""

from __future__ import annotations

import sys

from cesium_ios import *  # noqa: F401,F403  再导出，`import main as engine` 的老用法继续可用
from cesium_ios import (  # noqa: F401  包内部用的下划线名字，外部脚本/排查命令可能依赖
    _OUTPUT_HOOK,
    _Session,
    _ext_split,
    _house_arrest,
    _i32,
    _import_bundle_tool,
    _inside,
    _name_of,
    _plan_target,
    _pull_item,
    _read_object,
    _stamp,
    _zip_members,
)
from cesium_ios.cli import main  # noqa: F401  命令行入口（同 `cesium_ios.main`）


if __name__ == "__main__":
    sys.exit(main())
