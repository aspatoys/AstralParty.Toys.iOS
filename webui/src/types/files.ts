/** 文件 / 卡面 / 设置 —— 文件页的条目与结果、卡面方案、设置项。 */

import type { MarketState } from './market';

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

export type FsConflict = 'rename' | 'overwrite' | 'skip';

export type FsTransferMode = 'copy' | 'move';

export interface FsDropBatch {
  paths: string[];
  names: string[];
  at: number;
}

export interface FsOpenResult {
  path: string;
  local?: string;
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
  /** 本次运行的输出日志：本机 logs/ 下，一次运行一个文件。 */
  logFile: string;
  logDir: string;
}
