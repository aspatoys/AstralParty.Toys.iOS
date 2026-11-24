import type { FsEntry, FsTransferMode } from '../../types';

/** 只允许在 /Documents 下操作，这也是文件页的根。 */
export const ROOT = '/Documents';

/** 内部拖动的数据类型（用来和「从系统拖进来的文件」区分开）。 */
export const INTERNAL_DRAG = 'application/x-cesium-fs';

/** 列表列宽：和 FileTable 的行、列头共用。 */
export const SIZE_W = 96;
export const TIME_W = 132;

/** 行高（定高）：虚拟列表与框选的下标换算都按它算，必须和 FileTable 的样式一致。 */
export const ROW_H = 26;

export type SortKey = 'name' | 'size' | 'mtime';

export interface SortState {
  key: SortKey;
  dir: 1 | -1;
}

/** 框选用的矩形（viewport 坐标）。 */
export interface Box {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

/** 剪贴板：复制还是剪切（剪切 = 移动），以及当时选中的条目。 */
export interface Clipboard {
  mode: FsTransferMode;
  items: FsEntry[];
}

/** 粘贴时发现了同名项，等用户决定策略。 */
export interface ConflictPrompt {
  target: string;
  mode: FsTransferMode;
  count: number;
}

export interface RenameState {
  path: string;
  value: string;
}

export interface MenuState {
  x: number;
  y: number;
  entry: FsEntry | null;
}
