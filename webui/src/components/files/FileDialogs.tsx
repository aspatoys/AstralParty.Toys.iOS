import { useQuery } from '@tanstack/react-query';
import { Alert, Badge, Box, Button, Center, Group, Loader, Modal, ScrollArea, Stack, Text } from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconAlertTriangle } from '@tabler/icons-react';
import type { FsConflict, FsEntry } from '../../types';
import { formatBytes } from './format';
import type { FileBrowser } from './useFileBrowser';

/** 删除确认：列出前几项，目录会说明是递归删除。 */
export function confirmDelete(items: FsEntry[], onConfirm: () => void | Promise<void>) {
  if (!items.length) return;
  modals.openConfirmModal({
    title: '删除',
    children: (
      <Text size="sm">
        删除 {items.length} 个项目？
        {items.some((item) => item.dir) ? '（目录会连同里面的内容一起删除）' : ''}
        {items.length <= 6 ? (
          <Box component="ul" mt={6} mb={0} pl={18}>
            {items.map((item) => (
              <li key={item.path}>
                <Text size="xs" ff="monospace">
                  {item.name}
                </Text>
              </li>
            ))}
          </Box>
        ) : null}
      </Text>
    ),
    labels: { confirm: '删除', cancel: '取消' },
    confirmProps: { color: 'red' },
    onConfirm: () => void onConfirm(),
  });
}

/** 同名冲突的三种策略 + 文本预览。 */
export function FileDialogs({ browser }: { browser: FileBrowser }) {
  const { bridge, preview, conflict } = browser;

  const content = useQuery({
    queryKey: ['fsFile', preview?.path],
    queryFn: () => bridge.fs_file(preview!.path),
    enabled: !!preview,
  });

  return (
    <>
      <Modal
        opened={!!conflict}
        onClose={() => browser.setConflict(null)}
        title="目标位置已有同名项目"
        size="sm"
      >
        <Stack gap="sm">
          <Text size="sm">
            有 {conflict?.count} 个项目在 <code>{conflict?.target}</code> 里已经存在，要怎么处理？
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => void browser.resolveConflict('rename')}>
              保留两者
            </Button>
            <Button color="red" onClick={() => void browser.resolveConflict('overwrite')}>
              覆盖
            </Button>
            <Button variant="subtle" onClick={() => void browser.resolveConflict('skip')}>
              跳过
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={!!preview}
        onClose={() => browser.setPreview(null)}
        size="xl"
        title={
          <Group gap="xs">
            <Text size="sm" ff="monospace">
              {preview?.name}
            </Text>
            {content.data?.bytes != null && (
              <Badge size="xs" variant="default">
                {formatBytes(content.data.bytes)}
              </Badge>
            )}
          </Group>
        }
      >
        {content.isLoading ? (
          <Center h={200}>
            <Loader />
          </Center>
        ) : content.data?.error ? (
          <Alert color="red" icon={<IconAlertTriangle />}>
            {content.data.error}
          </Alert>
        ) : content.data?.binary ? (
          <Alert color="gray" icon={<IconAlertTriangle />}>
            二进制文件，不显示内容。
          </Alert>
        ) : content.data?.truncated ? (
          <Alert color="yellow" icon={<IconAlertTriangle />}>
            {content.data.note ?? '文件太大，只显示元信息。'}
          </Alert>
        ) : (
          <ScrollArea h={420}>
            <Text
              component="pre"
              fz={12}
              ff="monospace"
              m={0}
              style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
            >
              {content.data?.text ?? '(空)'}
            </Text>
          </ScrollArea>
        )}
      </Modal>
    </>
  );
}
