import { useCallback, useEffect, useRef, useState } from 'react';

interface Options {
  /** 条目总数。 */
  count: number;
  /** 行高（定高，行本身不换行）。 */
  rowHeight: number;
  /** 上下多渲染几行，滚动时不会看到空白。 */
  overscan?: number;
  /** 变化时回到顶部（换目录）。 */
  resetKey?: string;
}

/**
 * 手写的定高窗口化：目录里有几千上万个文件时只渲染可视区那几十行。
 *
 * 没引第三方虚拟列表依赖 —— 行高固定、没有动态测量，这点逻辑自己写更省事，
 * 也让「框选」可以直接用 `scrollTop / rowHeight` 算下标（见 `useSelection`）。
 */
export function useVirtualList({ count, rowHeight, overscan = 8, resetKey }: Options) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewport, setViewport] = useState(0);
  const frame = useRef(0);
  const pending = useRef(0);

  useEffect(() => {
    const element = listRef.current;
    if (!element) return;
    const update = () => setViewport(element.clientHeight);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // 滚动事件很密：一帧只更新一次状态，滚动不掉帧
  const onScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    pending.current = event.currentTarget.scrollTop;
    if (frame.current) return;
    frame.current = window.requestAnimationFrame(() => {
      frame.current = 0;
      setScrollTop(pending.current);
    });
  }, []);

  useEffect(() => () => {
    if (frame.current) window.cancelAnimationFrame(frame.current);
  }, []);

  // 换目录回到顶部（历史前进后退时也一样）
  useEffect(() => {
    const element = listRef.current;
    if (element) element.scrollTop = 0;
    setScrollTop(0);
  }, [resetKey]);

  const first = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visible = Math.ceil((viewport || rowHeight * 30) / rowHeight) + overscan * 2;
  const last = Math.min(count, first + visible);

  return {
    listRef,
    onScroll,
    first,
    last,
    rowHeight,
    paddingTop: first * rowHeight,
    paddingBottom: Math.max(0, (count - last) * rowHeight),
    virtualized: count > last - first,
  };
}
