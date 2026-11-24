/** 任务、设备与游戏 —— 任务槽状态、drain 结果、设备/游戏信息与探测结果。 */

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
