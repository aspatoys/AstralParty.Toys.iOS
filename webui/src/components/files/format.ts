import { ROOT } from './types';

export function formatBytes(bytes: number | null): string {
  if (bytes == null) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

/** 上一级目录；已经在 /Documents 时返回它自己。 */
export function parentOf(path: string): string {
  return path.replace(/\/[^/]+$/, '') || ROOT;
}

/** 路径最后一段（菜单文案里显示「粘贴到 xxx」用）。 */
export function baseName(path: string): string {
  const parts = path.split('/').filter(Boolean);
  return parts.length ? parts[parts.length - 1] : '/';
}

/** 两个名字是否指向同一层里的同一项（不用管大小写差异带来的干扰）。 */
export function sameName(left: string, right: string): boolean {
  return left.toLowerCase() === right.toLowerCase();
}
