/** 检测报告与模组 —— 概览页那份报告，以及模组清单、日志、配置读写的结果。 */

export interface LoaderInfo {
  present: boolean;
  root: string;
  /** 本机载荷目录（设备上那份东西的来源）。 */
  payload?: string;
  payload_present?: boolean;
  has_bootstrap?: boolean;
  /** 引导 DLL 是旧名（CesiumLoader.Android.Bootstrap.dll）—— 需重装一次加载器。 */
  bootstrap_stale?: boolean;
  bootstrap_dll?: string | null;
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

export type PatchState = 'patched' | 'patched-external' | 'clean' | 'stale' | 'unknown';

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
