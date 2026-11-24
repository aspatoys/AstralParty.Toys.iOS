import type { Bridge, ModInfo, Report } from '../types';

/**
 * 假桥：pnpm dev 直接在浏览器里开界面、或者设备没连上时用的演示数据。
 *
 * 方法名和 host/*_api.py 暴露的一致，所以页面代码不需要为「演示模式」写分支；
 * 判据是 isMock(bridge)（见 ./index）。
 */

/* ------------------------------------------------------------------ 假桥 */

const MOCK_MODS: ModInfo[] = (
  [
    ['ActivityLogMod', '实时行为日志', '2.3.0', 'Cesium'],
    ['CesiumOverlayMod', 'Cesium Android FloatingWindow', '1.0.0', 'TenkinMori/囚鱼玖'],
    ['CombatOddsMod', '战斗胜率', '2.8.7', 'Cesium'],
    ['FreeCameraMod', '自由相机', '1.6.0', 'Cesium'],
    ['HideHudMod', '隐藏 HUD', '1.2.0', 'Cesium'],
    ['LanguageUnlockMod', '语言解锁', '1.1.0', 'Cesium'],
    ['PinnedRelicsMod', '关键筹码置顶', '1.2.2', 'Cesium'],
    ['PvePanelMod', 'PVE 面板', '0.2.0', 'Cesium'],
    ['SpeedHackMod', '变速', '1.4.2', 'Cesium'],
    ['TurnClockMod', '回合时钟', '1.4.3', 'Cesium'],
    ['TurnFocusMod', '回合置前', '1.0.4', 'Cesium'],
    ['UnlockFrameRateMod', '帧率解锁', '1.1.0', 'Cesium'],
  ] as const
).map(([id, name, version, author], index) => ({
  id,
  enabled: index % 5 !== 4,
  dir: (index % 5 === 4 ? 'disabled_mods' : 'mods') as ModInfo['dir'],
  sidecar: {
    id,
    name,
    version,
    author,
    platforms: index % 4 === 1 ? ['android'] : ['windows', 'android'],
  },
  has_config: index % 3 !== 2,
  bytes: null,
}));

const MOCK_REPORT: Report = {
  bundle_id: 'com.feimo.astralpartycn',
  app_version: '3.3.0',
  catalog: 'catalog_3.3.0.json',
  catalog_build_hash: '6627ae5b7263798ca4371199373f12cc',
  code_bundle_hash: 'b0a50c4b443fb8fa6fe8f6dcecad029f',
  bundle_dir:
    '/Documents/com.unity.addressables/AssetBundles/4c3ac4ad220b44a5180ea3ede5fe520c/b0a50c4b443fb8fa6fe8f6dcecad029f',
  bundle_bytes: 8173962,
  bundle_mtime: '2026-11-24 01:26:15',
  bundle_sha256: '9ad935eb2ff2de74ef27fdb937524efc0757a5bb99585e995753a91301a18107',
  asset_count: 18,
  runtime_dll_bytes: 11705856,
  runtime_dll_sha256: '213ed3eabe517dd6abb605c85eed563316e6396ae51e59f27789f6fb1f3e8d7c',
  patch_state: 'patched-external',
  injected: true,
  loader: {
    present: true,
    root: '/Documents/CesiumLoader',
    has_bootstrap: true,
    bootstrap_dll: 'CesiumLoader.Mobile.Bootstrap.dll',
    bootstrap_stale: false,
    has_api: true,
    mod_count: MOCK_MODS.length,
    mods_ok: MOCK_MODS.length,
    mods_failed: 0,
    bootstrap_log: 'bootstrap-20261124-013219.log',
    bootstrap_tail: [
      'sdk loaded: CesiumLoader.SDK, Version=2.5.1.0',
      'mods found: 12',
      'done: ok=12 failed=0',
      'config poller: started',
    ],
  },
  markers: ['cesium_probe.txt', 'cesium_ios_s7_invoked.txt'],
  issues: [],
};

function delay<T>(value: T, ms = 260): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export function createMockBridge(): Bridge {
  let task = { name: null as string | null, running: false, ok: null as boolean | null, error: null as string | null };
  let mods = MOCK_MODS;

  const run = (name: string) => {
    task = { name, running: true, ok: null, error: null };
    setTimeout(() => {
      task = { name, running: false, ok: true, error: null };
    }, 1200);
    return { started: true, name };
  };

  return {
    __mock: true,
    drain: () => delay({ lines: [], task: { ...task } }, 0),
    probe: () =>
      delay({
        connected: true,
        device: { name: '（演示数据）iPhone', model: 'iPhone18,3', ios: '27.2', usb: 'USB' },
        game: { bundle_id: 'com.feimo.astralpartycn', version: '3.3.0', name: '吉星派对' },
      }),
    refresh: () => delay(run('检测')),
    get_report: () => delay(MOCK_REPORT),
    get_mods: () => delay(mods),
    set_mod_enabled: (id: string, enabled: boolean) => {
      mods = mods.map((m) => (m.id === id ? { ...m, enabled } : m));
      return delay(run(`${enabled ? '启用' : '停用'} ${id}`));
    },
    read_config: (id: string) =>
      delay({
        id,
        path: `/Documents/CesiumLoader/mods/${id}/config.json`,
        exists: true,
        text: `{\n  "enabled": true,\n  "hotkeyKey": "BackQuote"\n}\n`,
      }),
    write_config: (id: string, text: string) => delay(run(`保存 ${id} 配置`)).then(() => ({
      id,
      bytes: text.length,
    })),
    logs: () =>
      delay([
        { name: 'bootstrap-20261124-013219.log', bytes: 620, mtime: '2026-11-24 01:32:19' },
        { name: 'activity-mod-20261124-013219.log', bytes: 2731, mtime: '2026-11-24 01:32:19' },
      ]),
    read_log: (name: string) =>
      delay({ name, text: `（演示数据）\n${name}\ndone: ok=12 failed=0\nconfig poller: started\n` }),
    default_payload: () => delay('C:\\cesium\\payload\\CesiumLoader', 60),
    pick_folder: () => delay({ path: 'C:\\cesium\\payload\\CesiumLoader' }),
    install: () => delay(run('安装')),
    restore: (removeLoader: boolean) => delay(run(removeLoader ? '完全卸载' : '还原代码包')),

    market_state: () =>
      delay({
        baseUrl: 'https://forge.hiynet.com',
        consentVersion: 2,
        requiredVersion: 2,
        accepted: true,
      }),
    market_consent: (accepted: boolean) =>
      delay({
        baseUrl: 'https://forge.hiynet.com',
        consentVersion: accepted ? 2 : 0,
        requiredVersion: 2,
        accepted,
      }),
    set_market_base: (url: string) => delay({ ok: true, baseUrl: url }),
    market_list: () =>
      delay({
        ok: true,
        total: 3,
        page: 1,
        pageSize: 20,
        tags: ['玩法', '界面', '工具'],
        items: [
          {
            id: 'CombatOddsMod', name: '战斗胜率', summary: '对局中显示战斗胜率与伤害期望。',
            author: 'Cesium', tags: ['玩法'], coverUrl: null, latestVersion: '2.8.7',
            sdkVersion: '3.7.6', sizeBytes: 184320, sha256: '', downloadUrl: '',
            updatedAt: '2026-11-20', downloads: 12480, downloads7Days: 320,
            downloads30Days: 1400, featured: true, platforms: ['windows', 'android'],
          },
          {
            id: 'HandViewerMod', name: '手牌查看器', summary: '查看已知手牌与剩余牌库。',
            author: 'Cesium', tags: ['工具'], coverUrl: null, latestVersion: '1.4.0',
            sdkVersion: '3.7.6', sizeBytes: 96256, sha256: '', downloadUrl: '',
            updatedAt: '2026-11-10', downloads: 8300, downloads7Days: 120,
            downloads30Days: 900, featured: false, platforms: ['windows'],
          },
          {
            id: 'AttackNancyLuMod', name: 'Attack Nancy Lu', summary: '标点轮盘与集火提示增强。',
            author: 'hpenguins', tags: ['界面'], coverUrl: null, latestVersion: '1.1.0',
            sdkVersion: '3.8.10', sizeBytes: 51200, sha256: '', downloadUrl: '',
            updatedAt: '2026-11-22', downloads: 2100, downloads7Days: 60,
            downloads30Days: 300, featured: false, platforms: ['windows', 'android'],
          },
        ],
      }),
    market_detail: (id: string) =>
      delay({
        ok: true,
        detail: {
          id, name: id, summary: '（演示数据）', description: '这是一个演示用的模组详情。',
          author: 'Cesium', tags: ['玩法'], latestVersion: '1.0.0', downloads: 100,
          versions: [
            {
              version: '1.0.0', downloadUrl: '', sha256: '', sizeBytes: 102400,
              sdkVersion: '3.7.6', permissions: 0, changelog: '首个版本', publishedAt: '2026-11-20',
            },
          ],
        },
      }),
    market_install: (id: string) => delay(run(`安装 ${id}`)),

    fs: (path = '/Documents') =>
      delay({
        path,
        entries: [
          { name: 'CesiumLoader', path: `${path}/CesiumLoader`, dir: true, bytes: null, mtime: '' },
          { name: 'com.unity.addressables', path: `${path}/com.unity.addressables`, dir: true, bytes: null, mtime: '' },
          { name: 'DecodedBanks', path: `${path}/DecodedBanks`, dir: true, bytes: null, mtime: '' },
          { name: 'cesium_probe.txt', path: `${path}/cesium_probe.txt`, dir: false, bytes: 19, mtime: '2026-11-24 01:18' },
          { name: 'bootstrap.log', path: `${path}/bootstrap.log`, dir: false, bytes: 620, mtime: '2026-11-24 01:32' },
          { name: 'AstralParty.Runtime.dll.bak', path: `${path}/AstralParty.Runtime.dll.bak`, dir: false, bytes: 11761152, mtime: '2026-11-23 22:04' },
        ],
      }),
    fs_file: (path: string) =>
      delay({ path, bytes: 19, binary: false, truncated: false, text: '（演示数据）cesium ios probe ok\n' }),
    fs_open: (path: string) =>
      delay({ path, local: `C:\\Users\\shimikoi\\AppData\\Local\\Temp\\cesium-ios-open\\${path.split('/').pop()}` }),
    fs_mkdir: (_base: string, name: string) => delay(run(`新建文件夹 ${name}`)),
    fs_rename: (_path: string, name: string) => delay(run(`重命名为 ${name}`)),
    fs_delete: (paths: string | string[]) =>
      delay(run(`删除 ${Array.isArray(paths) ? paths.length : 1} 项`)),
    fs_transfer: (sources: string[], _target: string, mode = 'copy') =>
      delay(run(`${mode === 'move' ? '移动' : '复制'} ${sources.length} 项`)),
    fs_pick_dir: () => delay({ path: 'C:\\Users\\shimikoi\\Downloads' }, 60),
    fs_pick_files: () => delay({ paths: ['C:\\Users\\shimikoi\\Downloads\\deepseek_chan_1.zip'] }, 60),
    fs_download: (sources: string[]) => delay(run(`下载 ${sources.length} 项`)),
    fs_upload: (_target: string, localPaths?: string[] | null) =>
      delay(run(`上传 ${localPaths?.length ?? 1} 项`)),
    fs_drops: () => delay([], 0),

    skins: () =>
      delay({
        skins: [
          { name: 'default', path: '/Documents/CesiumLoader/skins/default', files: 198, cards: 198 },
          { name: 'deepseek_chan', path: '/Documents/CesiumLoader/skins/deepseek_chan', files: 186, cards: 186 },
        ],
      }),
    pick_zip: () => delay({ path: 'C:\\Users\\shimikoi\\OneDrive\\Downloads\\deepseek_chan_1.zip' }),
    skins_import: () => delay(run('导入卡面')),
    skins_activate: (name: string) => delay({ active: name, enabled: true }),
    open_logs: () => delay({ ok: true, path: 'C:\\src\\Study\\astralparty\\iOS\\logs' }, 60),
    pull_loader: () => delay(run('拉取最新 CesiumLoader')),
    settings: () =>
      delay({
        appVersion: '0.4.0',
        logFile: 'C:\\src\\Study\\astralparty\\iOS\\logs\\gui-20261124-112233.log',
        logDir: 'C:\\src\\Study\\astralparty\\iOS\\logs',
        payloadDefault: 'C:\\cesium\\payload\\CesiumLoader',
        market: {
          baseUrl: 'https://forge.hiynet.com',
          consentVersion: 2,
          requiredVersion: 2,
          accepted: true,
        },
      }),

    disconnect: () => delay({ ok: true }, 60),
    quit: () => delay(undefined, 60),
  } as unknown as Bridge;
}
