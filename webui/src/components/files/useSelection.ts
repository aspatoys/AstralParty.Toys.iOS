import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FsEntry } from '../../types';
import type { Box } from './types';

interface Options {
  entries: FsEntry[];
  path: string;
  /** 可聚焦的容器（资源管理器式的键盘操作靠它收键）。 */
  focusRef: React.RefObject<HTMLElement | null>;
  /** 滚动容器：定高窗口化之后，行位置直接由 scrollTop / rowHeight 推出来。 */
  scrollRef: React.RefObject<HTMLDivElement | null>;
  /** 行高（必须和 CSS 里的一致）。 */
  rowHeight: number;
  /** 选中动作之前先收尾，比如提交正在编辑的重命名。 */
  beforeSelect?: () => void;
}

/**
 * 选中状态：单击 / Ctrl+单击 / Shift 连选 / 空白处框选。
 *
 * 框选不查 DOM 行矩形，而是按 `scrollTop / rowHeight` 把鼠标的 Y 坐标换算成下标 ——
 * 这样配合虚拟列表也成立（屏幕外没有 DOM 行，但下标区间照样正确），而且每次
 * 鼠标移动是 O(选中行数) 而不是 O(目录条目数)。
 */
export function useSelection({
  entries, path, focusRef, scrollRef, rowHeight, beforeSelect,
}: Options) {
  const [selection, setSelection] = useState<string[]>([]);
  const [band, setBand] = useState<Box | null>(null);

  const anchorRef = useRef<string | null>(null);
  const bandRef = useRef<Box | null>(null);
  const bandBase = useRef<string[]>([]);
  const bandMode = useRef<'replace' | 'add'>('replace');
  const beforeRef = useRef(beforeSelect);
  beforeRef.current = beforeSelect;

  const byPath = useMemo(() => new Map(entries.map((entry) => [entry.path, entry])), [entries]);
  const selected = useMemo(() => new Set(selection), [selection]);
  const picked = useMemo(
    () => selection.map((item) => byPath.get(item)).filter(Boolean) as FsEntry[],
    [selection, byPath],
  );

  // 条目变了以后把已经不存在的选中项丢掉（删除 / 移动 / 改名之后会走到这里）
  useEffect(() => {
    setSelection((prev) => (prev.some((item) => !byPath.has(item))
      ? prev.filter((item) => byPath.has(item))
      : prev));
  }, [byPath]);

  useEffect(() => setSelection([]), [path]);

  const selectRange = useCallback((target: string) => {
    const anchor = anchorRef.current ?? target;
    const from = entries.findIndex((entry) => entry.path === anchor);
    const to = entries.findIndex((entry) => entry.path === target);
    if (from < 0 || to < 0) {
      setSelection([target]);
      return;
    }
    const [start, end] = from <= to ? [from, to] : [to, from];
    setSelection(entries.slice(start, end + 1).map((entry) => entry.path));
  }, [entries]);

  const onRowMouseDown = useCallback((event: React.MouseEvent, entry: FsEntry) => {
    if (event.button !== 0) return;
    focusRef.current?.focus();
    beforeRef.current?.();
    if (event.ctrlKey || event.metaKey) {
      anchorRef.current = entry.path;
      setSelection((prev) => (prev.includes(entry.path)
        ? prev.filter((item) => item !== entry.path)
        : [...prev, entry.path]));
      return;
    }
    if (event.shiftKey) {
      selectRange(entry.path);
      return;
    }
    if (!selected.has(entry.path)) {
      setSelection([entry.path]);
      anchorRef.current = entry.path;
    }
  }, [focusRef, selectRange, selected]);

  const selectAll = useCallback(() => setSelection(entries.map((entry) => entry.path)), [entries]);
  const clear = useCallback(() => setSelection([]), []);

  /* ------------------------------------------------------------ 框选 */

  const applyBand = useCallback((box: Box) => {
    const area = scrollRef.current;
    if (!area || !entries.length) return;
    const rect = area.getBoundingClientRect();
    const toIndex = (clientY: number) => {
      const raw = Math.floor((clientY - rect.top + area.scrollTop) / rowHeight);
      return Math.min(Math.max(raw, 0), entries.length - 1);
    };
    const from = toIndex(Math.min(box.y1, box.y2));
    const to = toIndex(Math.max(box.y1, box.y2));
    const merged = new Set(bandMode.current === 'replace' ? [] : bandBase.current);
    for (let index = from; index <= to; index += 1) merged.add(entries[index].path);
    setSelection([...merged]);
  }, [entries, rowHeight, scrollRef]);

  useEffect(() => {
    const move = (event: MouseEvent) => {
      const current = bandRef.current;
      if (!current) return;
      current.x2 = event.clientX;
      current.y2 = event.clientY;
      setBand({ ...current });
      applyBand(current);
      // 贴着上下边缘拖动时自动滚动，方便选长列表
      const area = scrollRef.current;
      if (!area) return;
      const rect = area.getBoundingClientRect();
      if (event.clientY < rect.top + rowHeight) area.scrollTop -= rowHeight * 2;
      else if (event.clientY > rect.bottom - rowHeight) area.scrollTop += rowHeight * 2;
    };
    const up = () => {
      if (!bandRef.current) return;
      bandRef.current = null;
      setBand(null);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
  }, [applyBand, rowHeight, scrollRef]);

  /** 在空白处按下才开始框选；按在行 / 按钮 / 输入框上不抢。 */
  const onBackgroundMouseDown = useCallback((event: React.MouseEvent) => {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest('[data-fs-row]') || target.closest('button') || target.closest('input')) return;
    focusRef.current?.focus();
    beforeRef.current?.();
    if (!event.ctrlKey && !event.metaKey) setSelection([]);
    bandMode.current = event.ctrlKey || event.metaKey ? 'add' : 'replace';
    bandBase.current = bandMode.current === 'add' ? selection : [];
    const box = { x1: event.clientX, y1: event.clientY, x2: event.clientX, y2: event.clientY };
    bandRef.current = box;
    setBand(box);
    event.preventDefault();
  }, [focusRef, selection]);

  return {
    selection,
    setSelection,
    selected,
    picked,
    byPath,
    anchorRef,
    selectRange,
    onRowMouseDown,
    onBackgroundMouseDown,
    selectAll,
    clear,
    band,
  };
}
