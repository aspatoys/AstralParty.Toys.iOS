import {
  ActionIcon, Badge, Breadcrumbs, Button, Divider, Group, Switch, Text, Tooltip, UnstyledButton,
} from '@mantine/core';
import {
  IconArrowLeft, IconArrowRight, IconArrowUp, IconClipboard, IconCopy, IconDownload,
  IconFileText, IconFolderPlus, IconPencil, IconRefresh, IconScissors, IconTrash, IconUpload,
} from '@tabler/icons-react';
import { ROOT } from './types';
import type { FileBrowser } from './useFileBrowser';

/** 面包屑 + 操作条 + 选中/剪贴板状态。 */
export function FileToolbar({ browser }: { browser: FileBrowser }) {
  const { picked, entries, selection, clipboard, dropTarget } = browser;

  return (
    <>
      <Group justify="space-between" wrap="nowrap">
        <Group gap={4} wrap="nowrap">
          <Tooltip label="后退（鼠标侧键 / Alt+←）">
            <ActionIcon variant="default" disabled={!browser.canBack} onClick={browser.back}>
              <IconArrowLeft size={16} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="前进（鼠标侧键 / Alt+→）">
            <ActionIcon variant="default" disabled={!browser.canForward} onClick={browser.forward}>
              <IconArrowRight size={16} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="上级目录（Backspace / Alt+↑）">
            <ActionIcon
              variant="default"
              disabled={browser.path === ROOT}
              onClick={browser.up}
            >
              <IconArrowUp size={16} />
            </ActionIcon>
          </Tooltip>
          <Breadcrumbs separator="/" separatorMargin={4}>
            {browser.trail.map((crumb, index) => (
              <UnstyledButton
                key={crumb.path}
                onClick={() => browser.navigate(crumb.path)}
                {...browser.breadcrumbHandlers(crumb.path)}
                style={{
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: dropTarget === crumb.path ? 'var(--mantine-color-blue-light)' : undefined,
                  fontWeight: index === browser.trail.length - 1 ? 600 : undefined,
                }}
              >
                <Text size="sm" ff="monospace">
                  {crumb.label}
                </Text>
              </UnstyledButton>
            ))}
          </Breadcrumbs>
        </Group>
        <Group gap="xs" wrap="nowrap">
          <Switch
            size="xs"
            label="显示隐藏项"
            checked={browser.showHidden}
            onChange={(event) => browser.setShowHidden(event.currentTarget.checked)}
          />
          <Badge size="xs" variant="light" color="gray">
            {clipboard
              ? `${clipboard.mode === 'copy' ? '复制' : '剪切'} ${clipboard.items.length} 项`
              : '剪贴板空'}
          </Badge>
        </Group>
      </Group>

      <Group gap={4} wrap="nowrap">
        <Tooltip label="新建文件夹">
          <ActionIcon variant="default" onClick={() => browser.setCreating('')}>
            <IconFolderPlus size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="上传本地文件到当前目录">
          <ActionIcon variant="default" onClick={() => void browser.upload()}>
            <IconUpload size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="下载选中项到本地目录">
          <ActionIcon variant="default" disabled={!picked.length} onClick={() => void browser.download(picked)}>
            <IconDownload size={16} />
          </ActionIcon>
        </Tooltip>
        <Divider orientation="vertical" />
        <Tooltip label="复制（Ctrl+C）">
          <ActionIcon variant="default" disabled={!picked.length} onClick={() => void browser.copy('copy')}>
            <IconCopy size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="剪切（Ctrl+X）">
          <ActionIcon variant="default" disabled={!picked.length} onClick={() => void browser.copy('move')}>
            <IconScissors size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="粘贴（Ctrl+V）">
          <ActionIcon variant="default" disabled={!clipboard} onClick={() => void browser.pasteInto(browser.path)}>
            <IconClipboard size={16} />
          </ActionIcon>
        </Tooltip>
        <Divider orientation="vertical" />
        <Tooltip label="重命名（F2）">
          <ActionIcon
            variant="default"
            disabled={picked.length !== 1}
            onClick={() => browser.setRenaming({ path: picked[0].path, value: picked[0].name })}
          >
            <IconPencil size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="预览文本">
          <ActionIcon
            variant="default"
            disabled={picked.length !== 1 || picked[0].dir}
            onClick={() => browser.setPreview(picked[0])}
          >
            <IconFileText size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="删除（Delete）">
          <ActionIcon
            variant="default"
            color="red"
            disabled={!picked.length}
            onClick={() => browser.remove(picked)}
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Tooltip>
        <Divider orientation="vertical" />
        <Button size="compact-xs" variant="subtle" disabled={!entries.length} onClick={browser.selectAll}>
          全选
        </Button>
        <Button
          size="compact-xs"
          variant="subtle"
          leftSection={<IconRefresh size={13} />}
          loading={browser.listing.isFetching}
          onClick={() => void browser.listing.refetch()}
        >
          刷新
        </Button>
        <Text size="xs" c="dimmed" ml="auto">
          {selection.length ? `已选 ${selection.length} / ` : ''}
          {entries.length} 项
        </Text>
      </Group>
    </>
  );
}
