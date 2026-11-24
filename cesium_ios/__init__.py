"""AstralParty.Toys.iOS 的引擎层（设备通道 + 容器内读写 + 各页面要用到的流程）。

`main.py` / `gui.py` 都从这里取功能：`import cesium_ios as engine`。
"""

from __future__ import annotations

from .paths import *  # noqa: F401,F403
from .output import *  # noqa: F401,F403
from .common import *  # noqa: F401,F403
from .device import *  # noqa: F401,F403
from .catalog import *  # noqa: F401,F403
from .patcher import *  # noqa: F401,F403
from .payload import *  # noqa: F401,F403
from .mods import *  # noqa: F401,F403
from .logs import *  # noqa: F401,F403
from .files import *  # noqa: F401,F403
from .skins import *  # noqa: F401,F403
from .report import *  # noqa: F401,F403
from .install import *  # noqa: F401,F403
from .cli import *  # noqa: F401,F403

# 下划线开头的是包内部用的工具；显式带上，避免 `main.<name>` 这类老写法失效
from .output import _OUTPUT_HOOK  # noqa: F401
from .device import _Session, _house_arrest  # noqa: F401
from .catalog import _i32, _read_object  # noqa: F401
from .patcher import _import_bundle_tool  # noqa: F401
from .files import _ext_split, _inside, _name_of, _plan_target, _pull_item  # noqa: F401

# 拆包时把这两个工具名去掉了下划线，旧名字留个别名
from .common import stamp as _stamp  # noqa: F401
from .common import zip_members as _zip_members  # noqa: F401
