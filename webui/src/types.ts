export interface Task {
  name: string | null;
  running: boolean;
  ok: boolean | null;
  error: string | null;
}

export interface DrainResult {
  lines: string[];
  task: Task;
}

export interface StartResult {
  started: boolean;
  name?: string;
  error?: string;
}

export interface DeviceInfo {
  name?: string;
  model?: string;
  ios?: string;
  usb?: string;
}

export interface GameInfo {
  bundle_id: string;
  version: string;
  name: string;
}

export interface Probe {
  connected: boolean;
  device?: DeviceInfo;
  game?: GameInfo;
  error?: string;
}

export interface LoaderInfo {
  present: boolean;
  root: string;
  has_bootstrap?: boolean;
  has_api?: boolean;
  mods?: string[];
  mod_count?: number;
  logs?: string[];
  bootstrap_log?: string;
  bootstrap_tail?: string[];
  mods_ok?: number;
  mods_failed?: number;
  mod_errors_log?: string;
}

export type PatchState = 'patched' | 'patched-external' | 'clean' | 'unknown';

export interface Report {
  bundle_id: string;
  app_version: string;
  catalog: string;
  catalog_build_hash: string;
  code_bundle_hash: string;
  bundle_dir: string;
  bundle_bytes: number;
  bundle_mtime: string;
  bundle_sha256: string;
  asset_count: number;
  runtime_dll_bytes: number;
  runtime_dll_sha256: string;
  patch_state: PatchState;
  injected: boolean;
  loader: LoaderInfo;
  markers: string[];
  issues: string[];
}

export interface Sidecar {
  id?: string;
  name?: string;
  version?: string;
  author?: string;
  description?: string;
  sdkVersion?: string;
  platforms?: string[];
  permissions?: number;
  dependencies?: string[];
  _parse_error?: string;
}

export interface ModInfo {
  id: string;
  enabled: boolean;
  dir: 'mods' | 'disabled_mods';
  sidecar: Sidecar | null;
  has_config: boolean;
  bytes: number | null;
}

export interface LogItem {
  name: string;
  bytes: number | null;
  mtime: string;
}

export interface ConfigResult {
  id: string;
  path?: string;
  text?: string;
  exists?: boolean;
  error?: string;
}

export interface WriteResult {
  id: string;
  path?: string;
  bytes?: number;
  error?: string;
}

export interface LogResult {
  name: string;
  text?: string;
  error?: string;
}

/* ------------------------------------------------------------------ 市场 */

export interface MarketState {
  baseUrl: string;
  consentVersion: number;
  requiredVersion: number;
  accepted: boolean;
}

export interface MarketItem {
  id: string;
  name: string;
  summary: string;
  author: string;
  tags: string[];
  coverUrl?: string | null;
  latestVersion: string;
  sdkVersion: string;
  sizeBytes: number;
  sha256: string;
  downloadUrl: string;
  updatedAt: string;
  downloads: number;
  downloads7Days: number;
  downloads30Days: number;
  featured: boolean;
  platforms: string[];
}

export interface MarketListResult {
  ok: boolean;
  error?: string;
  total?: number;
  page?: number;
  pageSize?: number;
  tags?: string[];
  items?: MarketItem[];
}

export interface MarketVersion {
  version: string;
  downloadUrl: string;
  sourceUrl?: string;
  hosted?: boolean;
  sha256?: string;
  sizeBytes?: number;
  sdkVersion?: string;
  permissions?: number;
  changelog?: string;
  publishedAt?: string;
  downloads?: number;
}

export interface MarketDetail {
  id: string;
  name: string;
  summary: string;
  description: string;
  author: string;
  tags: string[];
  repositoryUrl?: string;
  license?: string;
  readme?: string;
  coverUrl?: string | null;
  featured?: boolean;
  createdAt?: string;
  updatedAt?: string;
  latestVersion?: string;
  downloads?: number;
  versions?: MarketVersion[];
}

export interface MarketDetailResult {
  ok: boolean;
  error?: string;
  detail?: MarketDetail;
}

/* ------------------------------------------------------------------ 文件 / 卡面 / 设置 */

export interface FsEntry {
  name: string;
  path: string;
  dir: boolean;
  bytes: number | null;
  mtime: string;
}

export interface FsListResult {
  path: string;
  entries: FsEntry[];
  error?: string;
}

export interface FsFileResult {
  path: string;
  bytes?: number;
  binary?: boolean | null;
  truncated?: boolean;
  text?: string | null;
  note?: string;
  error?: string;
}

export interface SkinInfo {
  name: string;
  path: string;
  files: number;
  cards: number;
}

export interface SettingsResult {
  appVersion: string;
  payloadDefault: string;
  market: MarketState;
}

/** 宿主（gui.py 的 Api）对页面暴露的全部方法。 */
export interface Bridge {
  drain(): Promise<DrainResult>;
  probe(): Promise<Probe>;
  refresh(): Promise<StartResult>;
  get_report(): Promise<Report | null>;
  get_mods(): Promise<ModInfo[]>;
  set_mod_enabled(id: string, enabled: boolean): Promise<StartResult>;
  read_config(id: string, folder?: string | null): Promise<ConfigResult>;
  write_config(id: string, text: string, folder?: string | null): Promise<WriteResult>;
  logs(): Promise<LogItem[]>;
  read_log(name: string): Promise<LogResult>;
  default_payload(): Promise<string>;
  pick_folder(): Promise<{ path: string | null }>;
  install(payload: string | null, patch: boolean, deploy: boolean): Promise<StartResult>;
  restore(removeLoader: boolean): Promise<StartResult>;
  disconnect(): Promise<{ ok: boolean }>;
  quit(): Promise<void>;

  market_state(): Promise<MarketState>;
  market_consent(accepted: boolean): Promise<MarketState>;
  set_market_base(url: string): Promise<{ ok?: boolean; error?: string } & Partial<MarketState>>;
  market_list(page?: number, lang?: string): Promise<MarketListResult>;
  market_detail(id: string, lang?: string): Promise<MarketDetailResult>;
  market_install(id: string, version?: string | null, lang?: string): Promise<StartResult>;

  fs(path?: string, showHidden?: boolean): Promise<FsListResult>;
  fs_file(path: string): Promise<FsFileResult>;
  fs_delete(path: string): Promise<{ ok?: boolean; error?: string }>;

  skins(): Promise<{ skins: SkinInfo[]; error?: string }>;
  pick_zip(): Promise<{ path: string | null }>;
  skins_import(zip?: string | null, scheme?: string | null): Promise<StartResult>;
  skins_activate(name: string): Promise<{ active?: string; enabled?: boolean; error?: string }>;

  settings(): Promise<SettingsResult>;
}
