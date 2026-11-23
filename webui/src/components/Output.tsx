import { useEffect, useRef, useState } from 'react';
import { ActionIcon, Badge, Group, ScrollArea, Text } from '@mantine/core';
import { IconChevronDown, IconChevronUp, IconTrash } from '@tabler/icons-react';
import type { Task } from '../types';

interface Props {
  lines: string[];
  task: Task;
  onClear: () => void;
}

function lineColor(line: string): string | undefined {
  if (line.includes('[FAIL]')) return 'var(--mantine-color-red-6)';
  if (line.includes('[warn]')) return 'var(--mantine-color-yellow-6)';
  if (line.includes('[ok]')) return 'var(--mantine-color-teal-6)';
  if (line.includes('[task]')) return 'var(--mantine-color-blue-5)';
  return undefined;
}

export function Output({ lines, task, onClear }: Props) {
  const [open, setOpen] = useState(true);
  const viewport = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const element = viewport.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [lines, open]);

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
        <ScrollArea h={170} viewportRef={viewport} type="auto">
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
