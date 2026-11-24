import { useCallback, useEffect, useRef, useState } from 'react';
import { ActionIcon, Badge, Box, Group, ScrollArea, Text, Tooltip } from '@mantine/core';
import { IconChevronDown, IconChevronUp, IconFolderOpen, IconTrash } from '@tabler/icons-react';
import type { Task } from '../types';

interface Props {
  lines: string[];
  task: Task;
  onClear: () => void;
  /** 本次运行的输出日志（本机 logs/ 下，一次运行一个文件）。 */
  logFile?: string;
  onOpenLogs?: () => void;
}

const DEFAULT_HEIGHT = 170;
const MIN_HEIGHT = 90;
/** 上面至少要留给页面内容这么多像素，别把列表挤没了。 */
const RESERVED_TOP = 260;
const STORAGE_KEY = 'cesium-ios.outputHeight';

function maxHeight(): number {
  return Math.max(MIN_HEIGHT + 60, window.innerHeight - RESERVED_TOP);
}

function clampHeight(value: number): number {
  return Math.min(Math.max(Math.round(value), MIN_HEIGHT), maxHeight());
}

function loadHeight(): number {
  try {
    const raw = Number(window.localStorage?.getItem(STORAGE_KEY));
    if (!Number.isFinite(raw) || raw <= 0) return DEFAULT_HEIGHT;
    return clampHeight(raw);
  } catch {
    return DEFAULT_HEIGHT; // 隐私模式等拿不到 localStorage
  }
}

function saveHeight(value: number): void {
  try {
    window.localStorage?.setItem(STORAGE_KEY, String(value));
  } catch {
    /* 存不上不影响使用 */
  }
}

function lineColor(line: string): string | undefined {
  if (line.includes('[FAIL]')) return 'var(--mantine-color-red-6)';
  if (line.includes('[warn]')) return 'var(--mantine-color-yellow-6)';
  if (line.includes('[ok]')) return 'var(--mantine-color-teal-6)';
  if (line.includes('[task]')) return 'var(--mantine-color-blue-5)';
  return undefined;
}

export function Output({ lines, task, onClear, logFile, onOpenLogs }: Props) {
  const [open, setOpen] = useState(true);
  const [height, setHeight] = useState(loadHeight);
  const viewport = useRef<HTMLDivElement>(null);
  const dragging = useRef<{ startY: number; startHeight: number } | null>(null);
  const heightRef = useRef(height);
  heightRef.current = height;

  useEffect(() => {
    if (!open) return;
    const element = viewport.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [lines, open]);

  // 拖动上边缘改高度：整条监听挂在 window 上，鼠标移出面板也不会丢
  useEffect(() => {
    const move = (event: MouseEvent) => {
      const start = dragging.current;
      if (!start) return;
      setHeight(clampHeight(start.startHeight + (start.startY - event.clientY)));
    };
    const up = () => {
      if (!dragging.current) return;
      dragging.current = null;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      saveHeight(heightRef.current);
    };
    // 窗口变小的时候别让面板比窗口还高
    const resize = () => setHeight((value) => clampHeight(value));
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      window.removeEventListener('resize', resize);
    };
  }, []);

  const startResize = useCallback((event: React.MouseEvent) => {
    if (event.button !== 0) return;
    dragging.current = { startY: event.clientY, startHeight: heightRef.current };
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ns-resize';
    event.preventDefault();
  }, []);

  const applyHeight = (next: number) => {
    const value = clampHeight(next);
    setHeight(value);
    saveHeight(value);
  };

  const stateBadge = task.running ? (
    <Badge size="xs" color="blue" variant="light">
      {task.name} 运行中
    </Badge>
  ) : task.ok === true ? (
    <Badge size="xs" color="teal" variant="light">
      {task.name} 完成
    </Badge>
  ) : task.ok === false ? (
    <Badge size="xs" color="red" variant="light">
      {task.name} 失败
    </Badge>
  ) : (
    <Badge size="xs" color="gray" variant="light">
      空闲
    </Badge>
  );

  return (
    <div style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>
      {open && (
        <Box
          role="separator"
          aria-orientation="horizontal"
          aria-label="拖动调整输出面板高度（双击复位）"
          tabIndex={0}
          onMouseDown={startResize}
          onDoubleClick={() => applyHeight(DEFAULT_HEIGHT)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowUp') applyHeight(heightRef.current + 16);
            if (event.key === 'ArrowDown') applyHeight(heightRef.current - 16);
          }}
          title="拖动调整高度，双击复位"
          style={{
            height: 6,
            cursor: 'ns-resize',
            background: 'transparent',
            outline: 'none',
          }}
        >
          <Box
            style={{
              height: 2,
              margin: '2px auto 0',
              width: 48,
              borderRadius: 2,
              background: 'var(--mantine-color-default-border)',
            }}
          />
        </Box>
      )}

      <Group justify="space-between" px="md" h={40} wrap="nowrap">
        <Group gap="xs" wrap="nowrap">
          <Text size="xs" fw={600} c="dimmed">
            输出
          </Text>
          {stateBadge}
          {task.error && (
            <Text size="xs" c="red" truncate maw={520}>
              {task.error}
            </Text>
          )}
        </Group>
        <Group gap={4} wrap="nowrap">
          {open && (
            <Text size="10px" c="dimmed">
              {height}px
            </Text>
          )}
          {logFile && (
            <Tooltip label={`输出同时写进 ${logFile}`}>
              <ActionIcon variant="subtle" size="sm" onClick={onOpenLogs} aria-label="打开日志目录">
                <IconFolderOpen size={14} />
              </ActionIcon>
            </Tooltip>
          )}
          <ActionIcon variant="subtle" size="sm" onClick={onClear} aria-label="清空输出">
            <IconTrash size={14} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={() => setOpen((value) => !value)}
            aria-label={open ? '收起输出' : '展开输出'}
          >
            {open ? <IconChevronDown size={14} /> : <IconChevronUp size={14} />}
          </ActionIcon>
        </Group>
      </Group>

      {open && (
        <ScrollArea h={height} viewportRef={viewport} type="auto">
          <Text
            component="pre"
            px="md"
            pb="sm"
            m={0}
            fz={12}
            ff="monospace"
            style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
          >
            {lines.length === 0 ? (
              <Text span c="dimmed">
                （暂无输出）
              </Text>
            ) : (
              lines.map((line, index) => (
                <div key={`${index}-${line.slice(0, 12)}`} style={{ color: lineColor(line) }}>
                  {line || ' '}
                </div>
              ))
            )}
          </Text>
        </ScrollArea>
      )}
    </div>
  );
}
