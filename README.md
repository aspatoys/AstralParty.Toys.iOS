# AstralParty.Toys.iOS

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

Python 依赖（`pymobiledevice3`、`UnityPy`、`pywebview`）声明在 `pyproject.toml`，`uv run` 首次执行会自动
建好 `.venv`、装齐依赖并写好 `uv.lock`，**不需要手动建虚拟环境或往系统 Python 里装东西**。

设备侧只需要用 App Store 正常安装游戏，**首次启动一次**让热更资源下载完成。

## 快速开始

### 1. 启动界面

Windows 上双击 `start.cmd`，或者在 PowerShell 里跑 ` ./start.ps1 ` —— 它会按 `pyproject.toml` 装好
Python 依赖、构建一次前端，然后打开界面：

```powershell
./start.ps1                 # 装依赖（缺 node_modules 时）+ 构建前端 + 启动界面
./start.ps1 -SkipBuild      # 没装 Node 时用这个：直接用仓库里的 webui/dist 启动
```

macOS / Linux：

```bash
uv run gui.py
```

### 2. 准备载荷

界面只负责把载荷推上设备，**载荷本身不在这个仓库里**（`payload/` 是加载器那边的构建产物）。
在「设置」→「维护」里点 **拉取最新 CesiumLoader**：工具从 CesiumLoader 官方 Release 取 SDK 与
全部模组，再从安卓发行包的 APK 资产里取引导 DLL，写进 `payload/CesiumLoader/`。
下载缓存在 `work/release/`；载荷里已有的配置（模组 `config.json`）和额外文件不会被覆盖。

也可以不用它，自己把加载器发行包解开到 `payload/CesiumLoader/`，内容就是「载荷布局」那一节列的。

没有载荷时界面会提示「容器里没有 CesiumLoader 目录」，点「一键安装」也会因为找不到载荷而失败
（底部输出里是「载荷目录不存在」）。已经有载荷时也可以在「设置」页指到别的目录。

### 3. 点「一键安装」

1. 用 USB 连上设备，并在设备上点「信任此电脑」；
2. 点右上角 **一键安装**：注入代码包 + 投放载荷一起做，进度和结果看底部输出；
3. 在设备上**完全退出游戏再启动**。

命令行入口仍然保留（`uv run main.py`，交互式菜单），见「命令行」。

## 图形界面

```bash
uv run gui.py
```

Windows 上推荐用 `start.ps1`（或双击 `start.cmd`）：它会先 `pnpm build` 重新构建前端，再启动界面，
省得改完页面前忘了构建：

```powershell
./start.ps1                 # 装依赖（缺 node_modules 时）+ 构建前端 + 启动
./start.ps1 -SkipBuild      # 跳过构建，直接用现有的 webui/dist 启动
./start.ps1 -Smoke 6        # 起来 6 秒后自动关窗（冒烟用）
```

| 页面 | 内容 |
|---|---|
| 概览 | 设备与游戏、catalog、代码包（哈希 / 大小 / 资产数）、补丁状态、加载器、上次启动的 ok/failed、引导日志尾部、注入标记 |
| 模组 | 全部模组（启用状态、版本、作者、平台）；点开关启停，点「编辑」直接改该模组的 `config.json` |
| 市场 | 首次进入需同意免责声明（不同意就完全不连市场）；列表、详情、按版本安装 |
| 自定义 | 卡面方案：列出 `skins/` 里的方案、导入 ZIP、把某个方案设为启用（写 `CardSkinMod` 的 `ActiveSkin`） |
| 文件 | 设备容器 `/Documents` 的文件管理器：框选与多选、复制 / 剪切 / 粘贴、删除、重命名、拖动移动、上传下载 |
| 设置 | 市场地址与免责声明状态、安装 / 还原 / 卸载（维护）、关于 |

「文件」页按资源管理器的习惯操作：

- **选择**：单击选中，`Ctrl` / `⌘` 加选或反选，`Shift` 连选，在空白处按住拖动**框选**（`Ctrl` 拖动累加）；
  `Ctrl+A` 全选，`Esc` 取消，`Backspace` 回上级。
- **前进后退**：鼠标侧键（X1 / X2）就是后退 / 前进，工具条上的 ← → 与 `Alt+←` / `Alt+→` 等价，`Alt+↑` 回上级。
- **复制粘贴**：`Ctrl+C` / `Ctrl+X` / `Ctrl+V`，右键菜单同样有。粘贴时目标里若有同名项，会问
  「保留两者 / 覆盖 / 跳过」。
- **拖动**：把选中的行拖到文件夹行或面包屑上 = 移动（设备端 `rename`，不经过电脑）；
  把电脑上的文件 / 文件夹拖进窗口 = 上传到当前目录（拖到文件夹行上就是传到那个文件夹），同名覆盖。
- **双击**：目录进入；文件先下载到系统临时目录（`%TEMP%\cesium-ios-open`），再用系统默认程序打开。
- **下载 / 上传**：工具条上下载到自选目录、上传本地文件，全部走设备通道；目录与文件都支持。
- 列表可按名称 / 大小 / 修改时间排序，目录始终排在文件前面；`F2` 重命名、`Delete` 删除、`Ctrl+R` 刷新。

大目录也能用：列表按行高窗口化，只渲染看得见的那几十行，框选按行下标算；设备侧列目录时
各项属性是并发取的，几千个文件也是秒级。

所有要等设备的操作都有加载态：按钮转圈、整页骨架屏、开关行内加载指示、底部实时输出。
市场与卡面导入属于长任务，进度写在底部输出里，完成或失败会弹通知。

底部输出面板会记住高度：拖它的上边缘改高度（双击复位，聚焦后按 ↑/↓ 微调），折叠状态由标题栏右侧的箭头控制。
面板里的每一行也同时写进本机 `logs/`：`logs/gui-<yyyyMMdd-HHmmss>.log`（命令行是 `logs/cli-…`），
每行带 `HH:MM:SS` 时间戳，只保留最近 20 份；面板右上角的文件夹按钮可以直接打开日志目录。

启停就是搬目录（`mods/` ↔ `disabled_mods/`），界面状态以目录为准，不看 sidecar 里的 `enabled`。
配置按整段文本编辑并原样写回（不重新序列化，注释与写法都保留），保存前会校验能否解析回 JSON 对象。
市场列表与详情由宿主侧发起 HTTP（不走页面 `fetch`），因此不受跨域限制。

界面用 React + TypeScript + Vite 写，组件库是 Mantine（主色取自启动图标的莓红）。`webui/dist/` 是预构建产物，
**不装 Node 也能直接跑**；改前端才需要进入 `webui/` 执行 `pnpm install && pnpm build`。

Windows 上界面用的是 **WebView2**（与 AstralParty.Toys 同一个引擎），需要系统装有 WebView2
Runtime —— Windows 10/11 通常自带。

## 命令行

不带子命令时进交互式菜单：

```
uv run main.py

  1) 检测（设备 / 游戏 / catalog / 缓存 / 加载器 / 补丁状态）
  2) 安装或更新（注入代码包 + 投放载荷）
  3) 仅注入代码包
  4) 仅投放载荷
  5) 还原代码包（保留加载器）
  6) 完全卸载（还原 + 删除加载器）
  0) 退出
```

也可以用子命令：

```
uv run main.py detect [--json]
uv run main.py install [--payload <目录>] [--skip-payload] [--skip-patch]
uv run main.py pull [--payload <目录>] [--no-android] [--force-android]
uv run main.py restore [--keep-loader]
uv run main.py uninstall
```

`pull` 和界面里的「拉取最新 CesiumLoader」是同一套逻辑：从官方 Release 取 SDK 与全部模组，再从
安卓发行的 APK 里取引导 DLL；`--no-android` 只更新 SDK 与模组，`--force-android` 连引导 DLL 一起更新。
想走 GitHub 镜像时设 `CESIUM_GH_MIRROR=<前缀>`（拼在原地址前面）。

不想用 uv，就给同一个解释器装依赖再直接跑：

```bash
pip install pymobiledevice3 UnityPy==1.25.3 pywebview
python main.py
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
├─ CesiumLoader.Android.Bootstrap.dll   引导程序集（与安卓端同一份，来自安卓发行包的 APK）
├─ CesiumAndroidApi.dll                 悬浮窗 API（可选，同上）
├─ sdk/CesiumLoader.SDK.dll             模组 SDK（来自 CesiumLoader 官方 Release）
└─ mods/<ModId>/
   ├─ <ModId>.dll
   ├─ <ModId>.json                      sidecar（id/版本/权限/平台）
   ├─ config.json                       玩家配置
   └─ data/、sounds/、icons/…            模组自己的资源
```

在设备上，这套东西落在 `<容器>/Documents/CesiumLoader/`，`logs/`、`data/`、`disabled_mods/`
等目录由引导在启动时创建。

**SDK 必须是「没有 user32 也能跑」的构建**：iOS 上没有 `user32.dll` / `winmm`，只会走 Win32
后端的 SDK 会让热键模组每帧抛 `DllNotFoundException`，游戏卡在大厅里。带 Unity 兜底的构建里
有 `MobilePlatform.MarkNativeUnavailable`，投放前的检查就认这个标记；不满足时「一键安装」会
直接拒绝并说明原因（确实要原样投可用 `CESIUM_ALLOW_DESKTOP_SDK=1` 绕过）。「拉取最新
CesiumLoader」也不会把这种 SDK 写进载荷，而是保留载荷里原有的那份。

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
AstralParty.Toys.iOS/
├─ pyproject.toml               依赖与 Python 版本（`uv run` 会自动建 .venv、写 uv.lock）
├─ uv.lock                      锁定的依赖版本
├─ main.py                      CLI 入口；再导出 cesium_ios，`import main as engine` 仍可用
├─ gui.py                       图形界面入口；窗口与 js_api 都在 host/ 里
├─ cesium_ios/                  设备与容器操作（按职责拆开）
│  ├─ paths.py / output.py / common.py      目录常量 / 输出 / state、哈希、子进程输出解码
│  ├─ device.py                 house_arrest 会话、设备与应用发现
│  ├─ catalog.py                Addressables catalog 解析、定位承载代码包的 bundle
│  ├─ patcher.py                注入器编译与调用、UnityFS 资产读写
│  ├─ payload.py                载荷整理与投放
│  ├─ mods.py / logs.py         模组清单与启停 / 日志读取
│  ├─ files.py                  文件管理（浏览、复制粘贴、上传下载、双击打开）
│  ├─ skins.py                  卡面方案
│  ├─ report.py                 检测报告汇总
│  ├─ release.py                拉取官方发行包（SDK / 模组 / 安卓引导 DLL）
│  ├─ install.py                安装 / 还原流程（CLI 与 GUI 共用）
│  └─ cli.py                    argparse、交互式菜单
├─ host/                        图形界面宿主（pywebview）
│  ├─ window.py                 建窗口、挂 js_api、启动
│  ├─ api.py                    把各页面 mixin 装成唯一的 js_api 对象
│  ├─ session.py                设备会话复用、任务槽、drain 轮询
│  ├─ mods_api.py / files_api.py / skins_api.py / market_api.py / install_api.py / drop_api.py
│  └─ market.py / util.py / loop.py / config.py       HTTP、序列化、事件循环、常量
├─ webui/                       界面源码（React + TS + Vite；dist/ 为预构建产物）
│  ├─ src/api/                  宿主桥与演示用假桥
│  ├─ src/types/                与宿主共享的类型（按域分开）
│  └─ src/components/files/     文件页：控制器 hook + 列表 / 工具条 / 菜单 / 弹窗
├─ start.ps1 / start.cmd        先构建前端再启动界面
├─ tools/
│  ├─ CesiumIosPatcher/         Mono.Cecil 注入器源码
│  ├─ bundle_assets.py          UnityFS 读写（UnityPy）
│  ├─ ios_afc.py                容器读写通道（ls/get/put/rm，排查用）
│  ├─ scan_cache.py             扫缓存并与 catalog 对账（排查用）
│  ├─ decode_catalog.py         解 Addressables catalog（排查用）
│  └─ find_code_bundle.py       由资产键反查承载它的 bundle（排查用）
├─ payload/CesiumLoader/        载荷（自行放入，不入库）
├─ backups/                     原始代码包备份
├─ logs/                        界面 / 命令行的输出日志（不入库，保留最近 20 份）
├─ work/                        解包 / 注入过程文件（不入库）
└─ state.json                   已装记录与本机缓存
```

`tools/` 下的排查脚本各自带 PEP 723 内联依赖声明（`uv run tools/xxx.py` 单独跑也行）；
它们要的包和 `pyproject.toml` 里的相同，所以共用同一个 `.venv`。

改完后端之后的静态检查：

```bash
uv run --group dev pyflakes cesium_ios host main.py gui.py
```

## 排查

| 现象 | 先看 |
|---|---|
| 报「容器里没有 CesiumLoader 目录」 | 载荷还没上去。到「设置」→「维护」点一下「拉取最新 CesiumLoader」（或自己把载荷放进 `payload/CesiumLoader/`），再点右上角「一键安装」 |
| 报「SDK 没有退回 Unity 后端的兜底」 | 载荷里的 `sdk/CesiumLoader.SDK.dll` 是只走 Win32 的旧构建，装上去热键模组会把游戏卡死。换加载器新版本里的 SDK（带 `MobilePlatform.MarkNativeUnavailable`）再投放 |
| `[FAIL] 缺少 Python 依赖` | 用 `uv run` 跑（会按 `pyproject.toml` 自动建 `.venv` 装依赖）；或给跑脚本的那个解释器装上 |
| `detect` 报「缓存里找不到当前代码包」 | 游戏还没把热更下完，启动一次等下载结束 |
| 补丁状态「未知（与本工具记录不符）」 | 游戏刚热更过，重跑一次安装 |
| 模组没生效 | `detect` 的「上次启动」行；`logs/mod-errors-*.log` 会指出是哪个模组 |
| 引导日志里 `sdk loaded` 之后没有 `mods found` | 载荷没放全，检查 `sdk/` 与 `mods/` |
| 连接不上设备 | 设备是否解锁并「信任此电脑」；Windows 上需要 Apple Mobile Device Service 在运行 |
| 界面上显示「（演示数据）」 | 没连上宿主桥（`gui.py` 没起来），页面回退到了假桥；用 `start.ps1` 重新启动 |
| 拖进窗口的文件没反应 | 底部输出里找 `[warn] 没能注册窗口拖放接收器`，那是宿主注册拖放监听失败 |

需要更细的设备侧操作时，`tools/ios_afc.py` 提供 `ls` / `walk` / `stat` / `exists` / `get` /
`put` / `rm`，路径以 `/Documents` 开头。

## 许可

AGPL-3.0，见 [LICENSE](LICENSE)。
