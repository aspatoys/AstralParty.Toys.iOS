import { Box, Center, Group, Loader, Skeleton, Stack, Text, TextInput, UnstyledButton } from '@mantine/core';
import { IconFile, IconFolder } from '@tabler/icons-react';
import type { FsEntry } from '../../types';
import { formatBytes } from './format';
import { ROW_H, SIZE_W, TIME_W, type SortKey } from './types';
import type { FileBrowser } from './useFileBrowser';

/** 行内输入框（重命名）要压到行高以内，不然会把定高列表撑变形。 */
const inlineInput = {
  input: { height: ROW_H - 6, minHeight: ROW_H - 6, paddingInline: 6 },
};

function SortHeader({ browser, label, column, width }: {
  browser: FileBrowser;
  label: string;
  column: SortKey;
  width?: number;
}) {
  return (
    <UnstyledButton
      onClick={() => browser.toggleSort(column)}
      style={{ width, flex: width ? undefined : 1, minWidth: 0 }}
    >
      <Group gap={4} wrap="nowrap">
        <Text size="xs" fw={600} c="dimmed">
          {label}
        </Text>
        {browser.sort.key === column && (
          <Text size="xs" c="dimmed">
            {browser.sort.dir === 1 ? '↑' : '↓'}
          </Text>
        )}
      </Group>
    </UnstyledButton>
  );
}

/**
 * 文件列表：列头（可排序）+ 定高窗口化的行 + 内联的新建 / 重命名输入框。
 *
 * 目录里可能有上万个文件，所以只渲染可视区那几十行（`useVirtualList`）；行的 Y 位置
 * 由 `index * ROW_H` 决定，框选因此可以直接按下标算。「新建文件夹」的输入框放在滚动区
 * 之外，免得给下标换算多带一个偏移量。
 */
export function FileTable({ browser }: { browser: FileBrowser }) {
  const { entries, selected, renaming, creating, opening, clipboard, dropTarget, virtual } = browser;
  const visible = entries.slice(virtual.first, virtual.last);

  return (
    <>
      <Group
        gap={8}
        wrap="nowrap"
        px={8}
        py={6}
        style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
      >
        <SortHeader browser={browser} label="名称" column="name" />
        <SortHeader browser={browser} label="大小" column="size" width={SIZE_W} />
        <SortHeader browser={browser} label="修改时间" column="mtime" width={TIME_W} />
      </Group>

      {creating !== null && (
        <Group
          gap={8}
          wrap="nowrap"
          px={8}
          h={ROW_H + 4}
          style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
        >
          <IconFolder size={16} color="var(--mantine-color-blue-5)" />
          <TextInput
            size="xs"
            variant="filled"
            autoFocus
            placeholder="新建文件夹"
            value={creating}
            styles={inlineInput}
            style={{ flex: 1 }}
            onChange={(event) => browser.setCreating(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void browser.commitCreate();
              if (event.key === 'Escape') browser.setCreating(null);
            }}
            onBlur={() => void browser.commitCreate()}
          />
        </Group>
      )}

      <Box
        ref={virtual.listRef}
        onScroll={virtual.onScroll}
        style={{ flex: 1, minHeight: 0, overflow: 'auto' }}
      >
        {browser.listing.isLoading && (
          <Stack gap="xs" p="xs">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} height={12} width={`${45 + ((index * 11) % 40)}%`} />
            ))}
          </Stack>
        )}

        {!browser.listing.isLoading && entries.length === 0 && (
          <Center mih={120}>
            <Text size="sm" c="dimmed">
              空目录 —— 可以把本地文件拖进来上传
            </Text>
          </Center>
        )}

        {/* 上下两块占位撑出总高度，中间只放看得见的行 */}
        <Box style={{ height: virtual.paddingTop }} />
        {visible.map((entry) => (
          <Row
            key={entry.path}
            browser={browser}
            entry={entry}
            isSelected={selected.has(entry.path)}
            isCut={clipboard?.mode === 'move'
              && clipboard.items.some((item) => item.path === entry.path)}
            isDropTarget={dropTarget === entry.path}
            isRenaming={renaming?.path === entry.path}
            isOpening={opening === entry.path}
          />
        ))}
        <Box style={{ height: virtual.paddingBottom }} />
      </Box>
    </>
  );
}

function Row({ browser, entry, isSelected, isCut, isDropTarget, isRenaming, isOpening }: {
  browser: FileBrowser;
  entry: FsEntry;
  isSelected: boolean;
  isCut: boolean;
  isDropTarget: boolean;
  isRenaming: boolean;
  isOpening: boolean;
}) {
  return (
    <Box
      data-fs-row={entry.path}
      draggable={!isRenaming}
      onMouseDown={(event) => browser.onRowMouseDown(event, entry)}
      onDoubleClick={() => browser.onRowDoubleClick(entry)}
      onContextMenu={(event) => browser.onRowContextMenu(event, entry)}
      onDragStart={(event) => browser.onRowDragStart(event, entry)}
      onDragEnd={browser.endDrag}
      onDragOver={(event) => browser.onRowDragOver(event, entry)}
      onDragLeave={() => browser.onRowDragLeave(entry)}
      onDrop={(event) => browser.onRowDrop(event, entry)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        height: ROW_H,
        padding: '0 8px',
        cursor: 'default',
        userSelect: 'none',
        opacity: isCut ? 0.45 : 1,
        background: isSelected
          ? 'var(--mantine-primary-color-light)'
          : isDropTarget
            ? 'var(--mantine-color-blue-light)'
            : undefined,
        outline: isDropTarget ? '1px dashed var(--mantine-color-blue-5)' : undefined,
      }}
    >
      <Group gap={8} wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
        {entry.dir ? (
          <IconFolder size={16} color="var(--mantine-color-blue-5)" />
        ) : (
          <IconFile size={16} color="var(--mantine-color-dimmed)" />
        )}
        {isRenaming && browser.renaming ? (
          <TextInput
            size="xs"
            variant="filled"
            autoFocus
            value={browser.renaming.value}
            styles={inlineInput}
            style={{ flex: 1 }}
            onChange={(event) => browser.setRenaming({ path: entry.path, value: event.currentTarget.value })}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void browser.commitRename();
              if (event.key === 'Escape') browser.setRenaming(null);
            }}
            onBlur={() => void browser.commitRename()}
            onClick={(event) => event.stopPropagation()}
          />
        ) : (
          <Text size="sm" ff="monospace" truncate>
            {entry.name}
          </Text>
        )}
      </Group>
      {isOpening && <Loader size={12} />}
      <Text size="xs" c="dimmed" w={SIZE_W} style={{ flex: 'none' }}>
        {entry.dir ? '—' : formatBytes(entry.bytes)}
      </Text>
      <Text size="xs" c="dimmed" w={TIME_W} style={{ flex: 'none' }}>
        {entry.mtime || '—'}
      </Text>
    </Box>
  );
}
