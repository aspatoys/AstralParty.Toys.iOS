import { Alert, Box, Center, Stack, Text } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import type { Bridge } from '../../types';
import { FileDialogs } from './FileDialogs';
import { FileMenu } from './FileMenu';
import { FileTable } from './FileTable';
import { FileToolbar } from './FileToolbar';
import { useFileBrowser } from './useFileBrowser';

interface Props {
  bridge: Bridge;
  enabled: boolean;
}

/**
 * 「文件」页：像资源管理器一样浏览设备容器的 `/Documents`。
 *
 * - 单击 / Ctrl+单击 / Shift 连选 / 空白处框选；Ctrl+A 全选，Esc 取消
 * - Ctrl+C/X/V 复制剪切粘贴（同名冲突会问：保留两者 / 覆盖 / 跳过）
 * - 双击文件 = 拉到临时目录并用系统默认程序打开；双击目录 = 进入
 * - 拖动行到文件夹或面包屑上 = 移动；把本地文件拖进窗口 = 上传到当前目录
 * - Delete 删除、F2 重命名、Enter 打开、Backspace 回上级、Ctrl+R 刷新
 *
 * 逻辑都在 `useFileBrowser`（控制器）与三个 hook 里，这个文件只负责排版。
 */
export function Files({ bridge, enabled }: Props) {
  const browser = useFileBrowser(bridge, enabled);

  const bandStyle = browser.band
    ? {
        left: Math.min(browser.band.x1, browser.band.x2),
        top: Math.min(browser.band.y1, browser.band.y2),
        width: Math.abs(browser.band.x2 - browser.band.x1),
        height: Math.abs(browser.band.y2 - browser.band.y1),
      }
    : null;

  return (
    <Stack gap="xs" h="100%" style={{ display: 'flex', flexDirection: 'column' }}>
      <FileToolbar browser={browser} />

      {!enabled && (
        <Alert color="yellow" icon={<IconAlertTriangle />}>
          设备没连上，文件页只读不可用。
        </Alert>
      )}

      {browser.listing.data?.error && (
        <Alert color="red" icon={<IconAlertTriangle />}>
          {browser.listing.data.error}
        </Alert>
      )}

      <Box
        ref={browser.rootRef}
        tabIndex={0}
        onKeyDown={browser.onKeyDown}
        onMouseDown={browser.onBackgroundMouseDown}
        onContextMenu={browser.onBlankContextMenu}
        onDragOver={browser.onContainerDragOver}
        onDragLeave={browser.onContainerDragLeave}
        onDrop={browser.onContainerDrop}
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          outline: 'none',
          border: `1px solid ${browser.externalHover ? 'var(--mantine-color-blue-5)' : 'var(--mantine-color-default-border)'}`,
          borderRadius: 'var(--mantine-radius-md)',
          overflow: 'hidden',
          background: browser.externalHover ? 'var(--mantine-color-blue-light)' : undefined,
        }}
      >
        <FileTable browser={browser} />

        {browser.externalHover && (
          <Center
            style={{
              position: 'absolute',
              inset: 0,
              pointerEvents: 'none',
              background: 'var(--mantine-color-blue-light)',
            }}
          >
            <Text size="sm" fw={600}>
              松开就把文件上传到 {browser.path}
            </Text>
          </Center>
        )}
      </Box>

      <Text size="xs" c="dimmed">
        双击文件 = 下载到临时目录并用默认程序打开；拖动行到文件夹或面包屑上 = 移动；把本地文件拖进窗口 =
        上传到当前目录（同名覆盖）。快捷键：Ctrl+C/X/V、Delete、F2、Enter、Ctrl+A、Backspace 上级。
      </Text>

      {bandStyle && (
        <Box
          style={{
            position: 'fixed',
            ...bandStyle,
            border: '1px solid var(--mantine-color-blue-5)',
            background: 'var(--mantine-color-blue-light)',
            opacity: 0.4,
            pointerEvents: 'none',
            zIndex: 400,
          }}
        />
      )}

      <FileMenu browser={browser} />
      <FileDialogs browser={browser} />
    </Stack>
  );
}
