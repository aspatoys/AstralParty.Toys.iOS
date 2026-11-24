import { useCallback, useState } from 'react';
import { notifications } from '@mantine/notifications';
import type { Bridge, FsConflict, FsEntry, FsTransferMode, StartResult } from '../../types';
import { confirmDelete } from './FileDialogs';
import { sameName } from './format';
import type { Clipboard, ConflictPrompt, RenameState } from './types';

interface Options {
  bridge: Bridge;
  path: string;
  showHidden: boolean;
  entries: FsEntry[];
  byPath: Map<string, FsEntry>;
  picked: FsEntry[];
}

/**
 * 文件页的所有「动作」：打开、复制/剪切/粘贴、删除、重命名、新建、上传、下载。
 *
 * 真正干活的是宿主（`host/files_api.py`），这里只负责组装参数、检查同名冲突、
 * 把长任务的启动结果翻成通知。设备侧的长任务在界面任务槽里串行跑，完成后由
 * App 统一让 query 失效，列表自然刷新。
 */
export function useFileOps({ bridge, path, showHidden, entries, byPath, picked }: Options) {
  const [clipboard, setClipboard] = useState<Clipboard | null>(null);
  const [conflict, setConflict] = useState<ConflictPrompt | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const [preview, setPreview] = useState<FsEntry | null>(null);
  const [renaming, setRenaming] = useState<RenameState | null>(null);
  const [creating, setCreating] = useState<string | null>(null);

  const start = useCallback((result: StartResult, title: string) => {
    if (result.started) return true;
    notifications.show({ title, message: result.error ?? '', color: 'red' });
    return false;
  }, []);

  /** 双击：目录进目录，文件拉到临时目录并用系统默认程序打开。 */
  const open = useCallback(async (entry: FsEntry) => {
    if (entry.dir) return;
    setOpening(entry.path);
    try {
      const result = await bridge.fs_open(entry.path);
      if (result.error) {
        notifications.show({ title: '打开失败', message: result.error, color: 'red', autoClose: 7000 });
      } else {
        notifications.show({
          title: '已交给默认程序打开',
          message: result.local ?? '',
          color: 'teal',
          autoClose: 4000,
        });
      }
    } finally {
      setOpening(null);
    }
  }, [bridge]);

  const move = useCallback(async (paths: string[], target: string) => {
    start(await bridge.fs_transfer(paths, target, 'move', 'rename'), '移动失败');
  }, [bridge, start]);

  const runTransfer = useCallback(async (target: string, mode: FsTransferMode, policy: FsConflict) => {
    if (!clipboard) return;
    const result = await bridge.fs_transfer(
      clipboard.items.map((item) => item.path), target, mode, policy);
    if (start(result, mode === 'move' ? '移动失败' : '复制失败') && mode === 'move') {
      setClipboard(null); // 剪切粘贴完就清空，和资源管理器一致
    }
  }, [bridge, clipboard, start]);

  /** 粘贴：先看目标里有没有同名项，有就先问策略。 */
  const pasteInto = useCallback(async (target: string) => {
    if (!clipboard?.items.length) return;
    const wanted = clipboard.items.map((item) => item.name);
    // 设备上是大小写不敏感的文件系统，重名判断也跟着不敏感
    const clash = (entry: FsEntry) => wanted.some((name) => sameName(name, entry.name));
    let existing: FsEntry[];
    if (target === path) {
      existing = entries.filter(clash);
    } else {
      const listing = await bridge.fs(target, showHidden);
      existing = (listing.entries ?? []).filter(clash);
    }
    if (existing.length) {
      setConflict({ target, mode: clipboard.mode, count: existing.length });
      return;
    }
    await runTransfer(target, clipboard.mode, 'rename');
  }, [bridge, clipboard, entries, path, runTransfer, showHidden]);

  const copy = useCallback(async (mode: FsTransferMode) => {
    if (!picked.length) return;
    setClipboard({ mode, items: picked });
    if (mode === 'copy') {
      // 顺手把设备路径写进系统剪贴板，方便贴到别的地方
      void navigator.clipboard?.writeText(picked.map((item) => item.path).join('\n')).catch(() => undefined);
    }
    notifications.show({
      message: `${mode === 'copy' ? '已复制' : '已剪切'} ${picked.length} 项`,
      color: 'blue',
      autoClose: 1400,
    });
  }, [picked]);

  const remove = useCallback((items: FsEntry[]) => {
    if (!items.length) return;
    confirmDelete(items, async () => {
      start(await bridge.fs_delete(items.map((item) => item.path)), '删除失败');
    });
  }, [bridge, start]);

  const commitRename = useCallback(async () => {
    const current = renaming;
    if (!current) return;
    setRenaming(null);
    const entry = byPath.get(current.path);
    const value = current.value.trim();
    if (!entry || !value || value === entry.name) return;
    start(await bridge.fs_rename(current.path, value), '重命名失败');
  }, [bridge, byPath, renaming, start]);

  const commitCreate = useCallback(async () => {
    const name = (creating ?? '').trim();
    setCreating(null);
    if (!name) return;
    start(await bridge.fs_mkdir(path, name), '新建文件夹失败');
  }, [bridge, creating, path, start]);

  const upload = useCallback(async () => {
    const chosen = await bridge.fs_pick_files();
    if (!chosen.paths?.length) return;
    start(await bridge.fs_upload(path, chosen.paths, 'overwrite'), '上传失败');
  }, [bridge, path, start]);

  const download = useCallback(async (items: FsEntry[]) => {
    if (!items.length) return;
    const target = await bridge.fs_pick_dir('下载到');
    if (!target.path) return;
    start(await bridge.fs_download(items.map((item) => item.path), target.path), '下载失败');
  }, [bridge, start]);

  /** 冲突弹窗里选完策略后接着做。 */
  const resolveConflict = useCallback(async (policy: FsConflict) => {
    const current = conflict;
    setConflict(null);
    if (current) await runTransfer(current.target, current.mode, policy);
  }, [conflict, runTransfer]);

  return {
    clipboard,
    conflict,
    setConflict,
    resolveConflict,
    opening,
    preview,
    setPreview,
    renaming,
    setRenaming,
    commitRename,
    creating,
    setCreating,
    commitCreate,
    open,
    move,
    pasteInto,
    copy,
    remove,
    upload,
    download,
    start,
  };
}
