import { useCallback, useEffect, useRef, useState } from 'react';
import { notifications } from '@mantine/notifications';
import type { Bridge, FsEntry } from '../../types';
import { parentOf } from './format';
import { INTERNAL_DRAG } from './types';

interface Options {
  bridge: Bridge;
  enabled: boolean;
  path: string;
  /** 当前目录的实时值（拖放回调与轮询都在事件里读）。 */
  pathRef: React.MutableRefObject<string>;
  selected: Set<string>;
  selection: string[];
  setSelection: (paths: string[]) => void;
  move: (paths: string[], target: string) => Promise<void>;
}

/**
 * 拖动相关：
 *
 * - **界面内拖动**：把选中的行拖到文件夹行 / 面包屑上 = 移动（AFC rename，设备端原子操作）。
 * - **从系统拖进来**：WebView2 的 drop 事件拿不到完整本地路径，路径由宿主的
 *   pywebview DOM 监听带出来（见 `host/drop_api.py`），这里轮询队列再上传。
 */
export function useDragDrop({
  bridge, enabled, path, pathRef, selected, selection, setSelection, move,
}: Options) {
  const dragRef = useRef<string[]>([]);
  const dropDirRef = useRef<string>(path);
  const pendingDrops = useRef(0);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [externalHover, setExternalHover] = useState(false);

  const internalPaths = (event: React.DragEvent): string[] => {
    if (dragRef.current.length) return dragRef.current;
    try {
      const raw = event.dataTransfer.getData(INTERNAL_DRAG);
      const parsed = raw ? (JSON.parse(raw) as string[]) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const endDrag = useCallback(() => {
    dragRef.current = [];
    setDropTarget(null);
  }, []);

  const onRowDragStart = useCallback((event: React.DragEvent, entry: FsEntry) => {
    const paths = selected.has(entry.path) ? [...selection] : [entry.path];
    if (!selected.has(entry.path)) setSelection([entry.path]);
    dragRef.current = paths;
    event.dataTransfer.setData(INTERNAL_DRAG, JSON.stringify(paths));
    event.dataTransfer.setData('text/plain', paths.join('\n'));
    event.dataTransfer.effectAllowed = 'copyMove';
  }, [selected, selection, setSelection]);

  const registerExternalDrop = (target: string) => {
    dropDirRef.current = target;
    pendingDrops.current += 1;
    setExternalHover(false);
    setDropTarget(null);
    notifications.show({ message: `正在接收拖入的文件 → ${target}`, color: 'blue', autoClose: 1800 });
  };

  const onRowDrop = (event: React.DragEvent, entry: FsEntry) => {
    if (event.dataTransfer.types.includes(INTERNAL_DRAG)) {
      event.preventDefault();
      event.stopPropagation();
      const paths = internalPaths(event);
      endDrag();
      const target = entry.dir ? entry.path : path;
      if (paths.length && !paths.every((item) => parentOf(item) === target)) {
        void move(paths, target);
      }
      return;
    }
    if (event.dataTransfer.types.includes('Files')) {
      event.preventDefault();
      event.stopPropagation();
      registerExternalDrop(entry.dir ? entry.path : path);
    }
  };

  const onRowDragOver = (event: React.DragEvent, entry: FsEntry) => {
    if (!entry.dir || !event.dataTransfer.types.includes(INTERNAL_DRAG)) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'move';
    setDropTarget(entry.path);
  };

  const onRowDragLeave = (entry: FsEntry) => {
    setDropTarget((prev) => (prev === entry.path ? null : prev));
  };

  const onContainerDrop = (event: React.DragEvent) => {
    if (event.dataTransfer.types.includes(INTERNAL_DRAG)) {
      event.preventDefault();
      const paths = internalPaths(event);
      endDrag();
      if (paths.length && !paths.every((item) => parentOf(item) === path)) {
        void move(paths, path);
      }
      return;
    }
    if (event.dataTransfer.types.includes('Files')) {
      event.preventDefault();
      registerExternalDrop(path);
    }
  };

  const onContainerDragOver = (event: React.DragEvent) => {
    if (event.dataTransfer.types.includes('Files')) {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'copy';
      setExternalHover(true);
    }
  };

  const onContainerDragLeave = (event: React.DragEvent) => {
    // 只在真正离开容器时收起高亮（子元素的 dragleave 不算）
    if (event.currentTarget === event.target) setExternalHover(false);
  };

  /** 面包屑也能当拖动目标（拖到上一级很常见）。 */
  const breadcrumbHandlers = (target: string) => ({
    onDragOver: (event: React.DragEvent) => {
      if (!event.dataTransfer.types.includes(INTERNAL_DRAG)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      setDropTarget(target);
    },
    onDragLeave: () => setDropTarget((prev) => (prev === target ? null : prev)),
    onDrop: (event: React.DragEvent) => {
      if (!event.dataTransfer.types.includes(INTERNAL_DRAG)) return;
      event.preventDefault();
      event.stopPropagation();
      const paths = internalPaths(event);
      endDrag();
      if (paths.length) void move(paths, target);
    },
  });

  // 系统拖进来的路径只有宿主拿得到，这里轮询队列；目标目录用最近一次页面上的
  // drop 事件定（拖到文件夹行上就是那个文件夹），否则用当前目录。
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const timer = window.setInterval(async () => {
      if (!alive) return;
      try {
        const batches = await bridge.fs_drops();
        if (!alive || !batches?.length) return;
        for (const batch of batches) {
          const target = pendingDrops.current > 0 ? dropDirRef.current : pathRef.current;
          pendingDrops.current = Math.max(0, pendingDrops.current - 1);
          const result = await bridge.fs_upload(target, batch.paths, 'overwrite');
          if (!result.started) {
            notifications.show({ title: '上传失败', message: result.error ?? '', color: 'red' });
          }
        }
      } catch {
        /* 关闭窗口时会话会断，忽略 */
      }
    }, 700);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [bridge, enabled, pathRef]);

  return {
    dropTarget,
    externalHover,
    onRowDragStart,
    onRowDragOver,
    onRowDragLeave,
    onRowDrop,
    onContainerDragOver,
    onContainerDragLeave,
    onContainerDrop,
    breadcrumbHandlers,
    endDrag,
  };
}
