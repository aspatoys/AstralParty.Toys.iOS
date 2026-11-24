import type { DrainResult, Probe, StartResult, Task } from './common';
import type { FsConflict, FsDropBatch, FsFileResult, FsListResult, FsOpenResult, FsTransferMode,
  SettingsResult, SkinInfo } from './files';
import type { MarketDetailResult, MarketListResult, MarketState } from './market';
import type { ConfigResult, LogItem, LogResult, ModInfo, Report, WriteResult } from './report';

export * from './common';
export * from './files';
export * from './market';
export * from './report';

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
  fs_open(path: string): Promise<FsOpenResult>;
  fs_mkdir(base: string, name: string): Promise<StartResult>;
  fs_rename(path: string, name: string): Promise<StartResult>;
  fs_delete(paths: string | string[]): Promise<StartResult>;
  fs_transfer(
    sources: string[],
    target: string,
    mode?: FsTransferMode,
    conflict?: FsConflict,
  ): Promise<StartResult>;
  fs_pick_dir(title?: string): Promise<{ path: string | null }>;
  fs_pick_files(): Promise<{ paths: string[] }>;
  fs_download(sources: string[], localDir?: string | null): Promise<StartResult>;
  fs_upload(target: string, localPaths?: string[] | null, conflict?: FsConflict): Promise<StartResult>;
  fs_drops(): Promise<FsDropBatch[]>;

  skins(): Promise<{ skins: SkinInfo[]; error?: string }>;
  pick_zip(): Promise<{ path: string | null }>;
  skins_import(zip?: string | null, scheme?: string | null): Promise<StartResult>;
  skins_activate(name: string): Promise<{ active?: string; enabled?: boolean; error?: string }>;

  settings(): Promise<SettingsResult>;
  open_logs(): Promise<{ ok?: boolean; path: string; error?: string }>;
}
