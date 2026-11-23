# CesiumLoader iOS

在 iOS 上为《吉星派对 / Astral Party》加载 CesiumLoader 生态的模组。

**不需要越狱、不需要解密 IPA、不需要重签名。** 只要一台能用 USB 连上电脑的 iPhone / iPad。

## 工作原理

游戏的热更代码包（承载 `AstralParty.Runtime.dll` 的 Addressables bundle）**不在签名过的
`.app` 里**，而是运行时下载进 app 自身容器的数据文件。所以它不受代码签名约束，可以就地改写。

本工具做三件事：

1. 改写容器里的代码包，往 `AstralParty.Runtime.dll` 的 `<Module>` 静态构造里注入一小段引导调用
   （HybridCLR 会执行它，且这个锚点不依赖任何游戏方法形状，热更后不用重新找）；
2. 把加载器载荷投放到容器的 `<Documents>/CesiumLoader/`；
3. 游戏启动时，注入的引导从该目录加载 SDK 与模组。

容器读写走系统的 `com.apple.mobile.house_arrest` 服务（`VendDocuments`），这是 iOS 官方的
app 数据访问通道，桌面端工具常用的就是它。

## 环境要求

| 项 | 要求 |
|---|---|
| 设备 | iOS 设备，USB 连接并在设备上「信任此电脑」 |
| 桌面系统 | Windows / macOS / Linux |
| Python | 3.10 或更高 |
| [uv](https://docs.astral.sh/uv/) | 用来跑脚本并自动管理依赖 |
| .NET SDK | 8.0 或更高（首次运行会自动编译注入器） |

Python 依赖（`pymobiledevice3`、`UnityPy`）以 [PEP 723](https://peps.python.org/pep-0723/)
内联声明写在每个脚本头部，`uv run` 会自动装好，**不需要手动建虚拟环境或往系统 Python 里装东西**。

设备侧只需要用 App Store 正常安装游戏，**首次启动一次**让热更资源下载完成。

## 快速开始

```bash
# 1) 准备载荷：把加载器发行包解开，让 payload/CesiumLoader/ 里是下列内容
#      CesiumLoader.Android.Bootstrap.dll
#      CesiumAndroidApi.dll            （可选，悬浮窗用）
#      sdk/CesiumLoader.SDK.dll
#      mods/<ModId>/…

# 2) 跑交互式菜单
uv run main.py
```

不想用 uv，就给同一个解释器装依赖再直接跑：

```bash
pip install pymobiledevice3 UnityPy==1.25.3
uv run main.py
```

菜单：

```
  1) 检测（设备 / 游戏 / catalog / 缓存 / 加载器 / 补丁状态）
  2) 安装或更新（注入代码包 + 投放载荷）
  3) 仅注入代码包
  4) 仅投放载荷
  5) 还原代码包（保留加载器）
  6) 完全卸载（还原 + 删除加载器）
  0) 退出
```

装完在设备上**完全退出游戏再启动**即可。

## 图形界面

```bash
uv run gui.py
```

| 页签 | 内容 |
|---|---|
| 总览 | 设备与游戏、catalog、代码包（哈希 / 大小 / 资产数）、补丁状态、加载器、上次启动的 ok/failed、引导日志尾部、注入标记 |
| 模组 | 全部模组（启用状态、版本、作者、平台）；点开关启停，点「编辑」直接改该模组的 `config.json` |
| 日志 | `<加载器根目录>/logs/` 的文件列表与内容 |
| 操作 | 注入代码包 / 投放载荷 / 还原 / 完全卸载，底部是实时输出 |

启停就是搬目录（`mods/` ↔ `disabled_mods/`），界面状态以目录为准，不看 sidecar 里的 `enabled`。
配置按整段文本编辑并原样写回（不重新序列化，注释与写法都保留），保存前会校验能否解析回 JSON 对象。

Windows 上界面用的是 **WebView2**（与 AstralParty.Toys 同一个引擎），需要系统装有 WebView2
Runtime —— Windows 10/11 通常自带。

## 命令行

```
uv run main.py detect [--json]
uv run main.py install [--payload <目录>] [--skip-payload] [--skip-patch]
uv run main.py restore [--keep-loader]
uv run main.py uninstall
```

`detect` 输出示例：

```
=== 热更缓存里的代码包 ===
  目录        : /Documents/com.unity.addressables/AssetBundles/<外层>/<内层>
  大小        : 8173962 B
  sha256      : 9ad935eb…
  内含资产    : 18 个
  补丁状态    : 已注入（程序集内标记：有）

=== 加载器 ===
  模组        : 27 个
  上次启动    : ok=27 failed=0
  引导日志    : bootstrap-20261124-013219.log
```

`--json` 给脚本用。退出码：`0` 正常，`1` 出错（找不到设备/游戏），`2` 检测到问题。

## 载荷布局

`payload/CesiumLoader/` 的目录结构就是设备上加载器根目录的结构：

```
CesiumLoader/
├─ CesiumLoader.Android.Bootstrap.dll   引导程序集（与安卓端同一份）
├─ CesiumAndroidApi.dll                 悬浮窗 API（可选）
├─ sdk/CesiumLoader.SDK.dll             模组 SDK
└─ mods/<ModId>/
   ├─ <ModId>.dll
   ├─ <ModId>.json                      sidecar（id/版本/权限/平台）
   ├─ config.json                       玩家配置
   └─ data/、sounds/、icons/…            模组自己的资源
```

在设备上，这套东西落在 `<容器>/Documents/CesiumLoader/`，`logs/`、`data/`、`disabled_mods/`
等目录由引导在启动时创建。

## 模组启停

**状态只看目录**：`mods/` 是启用，`disabled_mods/` 是停用。搬目录即可，不需要改任何配置文件。
模组配置在 `mods/<ModId>/config.json`。

## 兼容性

- **包名**：按 `com.feimo.astralpartycn`、`com.feimo.astralparty`、`com.feimo.jxpd`、
  `com.feimo.astralparty.cesium` 的顺序自动识别。
- **容器范围**：App Store 应用的整个容器（`VendContainer`）会被设备拒绝，只能访问 `Documents`。
  游戏的热更缓存与加载器目录都在 `Documents` 下，所以不影响使用。
- **每次游戏热更后需要重跑一次安装**：代码包的内容哈希会变，本工具按 catalog 自动重新定位，
  旧包会被游戏清理掉。
- 模组由 HybridCLR 解释执行，与安卓端同一套托管程序集；模组里调用输入 / 音频的地方已按
  移动端处理（移动端没有 `user32.dll` / `winmm`）。

## 卸载与还原

```
uv run main.py restore      # 还原代码包，保留 CesiumLoader 目录
uv run main.py uninstall    # 还原代码包 + 删除 CesiumLoader 目录与标记文件
```

安装时会把原始代码包备份到 `backups/<哈希>.data`，`restore` 优先用它还原；
没有备份时删除缓存条目，游戏下次启动会重新下载原始包。

## 目录结构

```
CesiumLoader4iOS/
├─ main.py                     命令行：交互式安装 / 检测
├─ gui.py                      图形界面（pywebview）
├─ webui/                      界面（index.html / app.js / style.css）
├─ tools/
│  ├─ CesiumIosPatcher/        Mono.Cecil 注入器源码
│  ├─ bundle_assets.py         UnityFS 读写（UnityPy）
│  ├─ ios_afc.py               容器读写通道（ls/get/put/rm，排查用）
│  ├─ scan_cache.py            扫缓存并与 catalog 对账（排查用）
│  ├─ decode_catalog.py        解 Addressables catalog（排查用）
│  └─ find_code_bundle.py      由资产键反查承载它的 bundle（排查用）
├─ payload/CesiumLoader/       载荷（自行放入，不入库）
├─ backups/                    原始代码包备份
├─ work/                       解包 / 注入过程文件
└─ state.json                  已装记录与本机缓存
```

## 排查

| 现象 | 先看 |
|---|---|
| `[FAIL] 缺少 Python 依赖` | 用 `uv run` 跑（会自动装依赖）；或给跑脚本的那个解释器装上 |
| `detect` 报「缓存里找不到当前代码包」 | 游戏还没把热更下完，启动一次等下载结束 |
| 补丁状态「未知（与本工具记录不符）」 | 游戏刚热更过，重跑一次安装 |
| 模组没生效 | `detect` 的「上次启动」行；`logs/mod-errors-*.log` 会指出是哪个模组 |
| 引导日志里 `sdk loaded` 之后没有 `mods found` | 载荷没放全，检查 `sdk/` 与 `mods/` |
| 连接不上设备 | 设备是否解锁并「信任此电脑」；Windows 上需要 Apple Mobile Device Service 在运行 |

需要更细的设备侧操作时，`tools/ios_afc.py` 提供 `ls` / `walk` / `stat` / `exists` / `get` /
`put` / `rm`，路径以 `/Documents` 开头。

## 许可

AGPL-3.0，见 [LICENSE](LICENSE)。
