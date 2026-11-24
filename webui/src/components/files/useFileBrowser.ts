import { useCallback, useMemo, useRef, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { Bridge, FsEntry } from '../../types';
import { ROOT, ROW_H, type MenuState, type SortKey, type SortState } from './types';
import { useDragDrop } from './useDragDrop';
import { useFileOps } from './useFileOps';
import { useNavHistory } from './useNavHistory';
import { useSelection } from './useSelection';
import { useVirtualList } from './useVirtualList';

/** 中文文件名排序用同一个 collator，比每次 localeCompare 快不少（大目录很明显）。 */
const collator = new Intl.Collator('zh-Hans-CN', { numeric: true, sensitivity: 'variant' });

/**
 * 文件页的控制器：把「列表数据」「目录历史」「选中」「动作」「拖放」拼在一起。
 *
 * 拆成多个 hook 之后有一个循环依赖：选中动作要先提交正在编辑的重命名，而重命名状态
 * 在 `useFileOps` 里。这里用一个 ref 晚绑定解开，避免把两个 hook 揉成一个。
 */
export function useFileBrowser(bridge: Bridge, enabled: boolean) {
  const nav = useNavHistory(ROOT);
  const path = nav.path;
  const [showHidden, setShowHidden] = useState(false);
  const [sort, setSort] = useState<SortState>({ key: 'name', dir: 1 });
  const [menu, setMenu] = useState<MenuState | null>(null);

  const rootRef = useRef<HTMLDivElement | null>(null);

  const listing = useQuery({
    queryKey: ['fs', path, showHidden],
    queryFn: () => bridge.fs(path, showHidden),
    enabled,
    placeholderData: keepPreviousData,
  });

  // 目录永远排在文件前面，其余按当前列排序
  const entries = useMemo(() => {
    const list = [...(listing.data?.entries ?? [])];
    const factor = sort.dir;
    list.sort((a, b) => {
      if (a.dir !== b.dir) return a.dir ? -1 : 1;
      if (sort.key === 'size') {
        const delta = (a.bytes ?? 0) - (b.bytes ?? 0);
        if (delta) return delta * factor;
      } else if (sort.key === 'mtime') {
        const delta = (a.mtime || '').localeCompare(b.mtime || '');
        if (delta) return delta * factor;
      }
      return collator.compare(a.name, b.name) * factor;
    });
    return list;
  }, [listing.data, sort]);

  const virtual = useVirtualList({ count: entries.length, rowHeight: ROW_H, resetKey: path });

  const beforeSelect = useRef<() => void>(() => {});
  const select = useSelection({
    entries,
    path,
    focusRef: rootRef,
    scrollRef: virtual.listRef,
    rowHeight: ROW_H,
    beforeSelect: () => beforeSelect.current(),
  });
  const ops = useFileOps({
    bridge,
    path,
    showHidden,
    entries,
    byPath: select.byPath,
    picked: select.picked,
  });
  beforeSelect.current = () => {
    if (ops.renaming) void ops.commitRename();
  };

  const drag = useDragDrop({
    bridge,
    enabled,
    path,
    pathRef: nav.pathRef,
    selected: select.selected,
    selection: select.selection,
    setSelection: select.setSelection,
    move: ops.move,
  });

  const toggleSort = useCallback((key: SortKey) => {
    setSort((prev) => ({ key, dir: prev.key === key && prev.dir === 1 ? -1 : 1 }));
  }, []);

  const openEntry = useCallback((entry: FsEntry) => {
    if (entry.dir) nav.navigate(entry.path);
    else void ops.open(entry);
  }, [nav, ops]);

  const onRowDoubleClick = useCallback((entry: FsEntry) => {
    if (ops.renaming?.path === entry.path) return;
    openEntry(entry);
  }, [openEntry, ops.renaming]);

  const trail = useMemo(() => {
    const parts = path.split('/').filter(Boolean);
    return parts.map((part, index) => ({
      label: part,
      path: `/${parts.slice(0, index + 1).join('/')}`,
    }));
  }, [path]);

  /* ------------------------------------------------------------ 右键菜单 */

  const onRowContextMenu = useCallback((event: React.MouseEvent, entry: FsEntry) => {
    event.preventDefault();
    rootRef.current?.focus();
    if (!select.selected.has(entry.path)) select.setSelection([entry.path]);
    setMenu({ x: event.clientX, y: event.clientY, entry });
  }, [select]);

  const onBlankContextMenu = useCallback((event: React.MouseEvent) => {
    if ((event.target as HTMLElement).closest('[data-fs-row]')) return;
    event.preventDefault();
    rootRef.current?.focus();
    setMenu({ x: event.clientX, y: event.clientY, entry: null });
  }, []);

  const closeMenu = useCallback(() => setMenu(null), []);

  /** 右键点到文件夹就在文件夹里粘贴/新建，否则在当前目录。 */
  const menuTarget = menu?.entry?.dir ? menu.entry.path : path;
  const menuItems = menu?.entry ? (select.picked.length ? select.picked : [menu.entry]) : [];

  /* ------------------------------------------------------------ 键盘 */

  const onKeyDown = useCallback((event: React.KeyboardEvent) => {
    const target = event.target as HTMLElement;
    const typing = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;
    if (typing) {
      if (event.key === 'Escape' && ops.renaming) ops.setRenaming(null);
      if (event.key === 'Escape' && ops.creating !== null) ops.setCreating(null);
      return;
    }
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();
    if (event.altKey && event.key === 'ArrowLeft') {
      event.preventDefault();
      nav.back();
    } else if (event.altKey && event.key === 'ArrowRight') {
      event.preventDefault();
      nav.forward();
    } else if (event.altKey && event.key === 'ArrowUp') {
      event.preventDefault();
      nav.up();
    } else if (mod && key === 'a') {
      event.preventDefault();
      select.selectAll();
    } else if (mod && key === 'c') {
      event.preventDefault();
      void ops.copy('copy');
    } else if (mod && key === 'x') {
      event.preventDefault();
      void ops.copy('move');
    } else if (mod && key === 'v') {
      event.preventDefault();
      void ops.pasteInto(path);
    } else if (mod && key === 'r') {
      event.preventDefault();
      void listing.refetch();
    } else if (event.key === 'Delete') {
      event.preventDefault();
      ops.remove(select.picked);
    } else if (event.key === 'F2' && select.picked.length === 1) {
      event.preventDefault();
      ops.setRenaming({ path: select.picked[0].path, value: select.picked[0].name });
    } else if (event.key === 'Enter' && select.picked.length === 1) {
      event.preventDefault();
      openEntry(select.picked[0]);
    } else if (event.key === 'Escape') {
      select.clear();
      setMenu(null);
    } else if (event.key === 'Backspace') {
      event.preventDefault();
      nav.up();
    }
  }, [listing, nav, openEntry, ops, path, select]);

  return {
    bridge,
    enabled,
    path,
    showHidden,
    setShowHidden,
    sort,
    toggleSort,
    listing,
    entries,
    trail,
    rootRef,
    menu,
    menuItems,
    menuTarget,
    closeMenu,
    openEntry,
    onRowDoubleClick,
    onRowContextMenu,
    onBlankContextMenu,
    onKeyDown,
    virtual,
    navigate: nav.navigate,
    up: nav.up,
    back: nav.back,
    forward: nav.forward,
    canBack: nav.canBack,
    canForward: nav.canForward,
    ...select,
    ...ops,
    ...drag,
  };
}

/** 控制器返回的全部内容；各视图组件直接吃它，省掉几十个 props 的搬运。 */
export type FileBrowser = ReturnType<typeof useFileBrowser>;
