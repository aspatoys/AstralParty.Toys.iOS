import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ActionIcon, Alert, Badge, Box, Breadcrumbs, Button, Center, Group, Loader, Modal,
  ScrollArea, Skeleton, Stack, Switch, Table, Text, Tooltip, UnstyledButton,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle, IconArrowUp, IconFile, IconFolder, IconRefresh, IconTrash,
} from '@tabler/icons-react';
import type { Bridge, FsEntry } from '../types';

interface Props {
  bridge: Bridge;
  enabled: boolean;
}

function formatBytes(bytes: number | null): string {
  if (bytes == null) return '–';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

export function Files({ bridge, enabled }: Props) {
  const [path, setPath] = useState('/Documents');
  const [showHidden, setShowHidden] = useState(false);
  const [preview, setPreview] = useState<FsEntry | null>(null);

  const listing = useQuery({
    queryKey: ['fs', path, showHidden],
    queryFn: () => bridge.fs(path, showHidden),
    enabled,
  });

  const content = useQuery({
    queryKey: ['fsFile', preview?.path],
    queryFn: () => bridge.fs_file(preview!.path),
    enabled: !!preview,
  });

  const trail = useMemo(() => {
    const parts = path.split('/').filter(Boolean);
    return parts.map((part, index) => ({
      label: part,
      path: `/${parts.slice(0, index + 1).join('/')}`,
    }));
  }, [path]);

  const remove = (entry: FsEntry) =>
    modals.openConfirmModal({
      title: '删除',
      children: (
        <Text size="sm">
          删除 <code>{entry.path}</code>？
          {entry.dir ? '（整个目录会被递归删除）' : ''}
        </Text>
      ),
      labels: { confirm: '删除', cancel: '取消' },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        const result = await bridge.fs_delete(entry.path);
        if (result.error) {
          notifications.show({ title: '删除失败', message: result.error, color: 'red' });
          return;
        }
        notifications.show({ message: '已删除', color: 'teal', autoClose: 1500 });
        void listing.refetch();
      },
    });

  return (
    <Stack gap="sm">
      <Group justify="space-between" wrap="nowrap">
        <Breadcrumbs separator="/" separatorMargin={4}>
          {trail.map((crumb) => (
            <UnstyledButton key={crumb.path} onClick={() => setPath(crumb.path)}>
              <Text size="sm" ff="monospace">
                {crumb.label}
              </Text>
            </UnstyledButton>
          ))}
        </Breadcrumbs>
        <Group gap="xs" wrap="nowrap">
          <Switch
            size="xs"
            label="显示隐藏项"
            checked={showHidden}
            onChange={(event) => setShowHidden(event.currentTarget.checked)}
          />
          <Tooltip label="上级目录">
            <ActionIcon
              variant="default"
              onClick={() => setPath(path.replace(/\/[^/]+$/, '') || '/Documents')}
            >
              <IconArrowUp size={16} />
            </ActionIcon>
          </Tooltip>
          <Button
            size="compact-sm"
            variant="default"
            leftSection={<IconRefresh size={14} />}
            onClick={() => void listing.refetch()}
            loading={listing.isFetching}
          >
            刷新
          </Button>
        </Group>
      </Group>

      {listing.data?.error && (
        <Alert color="red" icon={<IconAlertTriangle />}>
          {listing.data.error}
        </Alert>
      )}

      <Box style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 'var(--mantine-radius-md)' }}>
        <Table highlightOnHover verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>名称</Table.Th>
              <Table.Th w={110}>大小</Table.Th>
              <Table.Th w={180}>修改时间</Table.Th>
              <Table.Th w={64} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {listing.isLoading &&
              Array.from({ length: 8 }).map((_, index) => (
                <Table.Tr key={index}>
                  <Table.Td><Skeleton height={10} width={`${40 + ((index * 9) % 40)}%`} /></Table.Td>
                  <Table.Td><Skeleton height={8} width={50} /></Table.Td>
                  <Table.Td><Skeleton height={8} width={90} /></Table.Td>
                  <Table.Td />
                </Table.Tr>
              ))}

            {!listing.isLoading && (listing.data?.entries ?? []).length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={4}>
                  <Center mih={90}>
                    <Text size="sm" c="dimmed">
                      空目录
                    </Text>
                  </Center>
                </Table.Td>
              </Table.Tr>
            )}

            {!listing.isLoading &&
              (listing.data?.entries ?? []).map((entry) => (
                <Table.Tr key={entry.path}>
                  <Table.Td>
                    <UnstyledButton
                      onClick={() => (entry.dir ? setPath(entry.path) : setPreview(entry))}
                      style={{ width: '100%' }}
                    >
                      <Group gap={8} wrap="nowrap">
                        {entry.dir ? (
                          <IconFolder size={16} color="var(--mantine-color-blue-5)" />
                        ) : (
                          <IconFile size={16} color="var(--mantine-color-dimmed)" />
                        )}
                        <Text size="sm" ff="monospace" truncate>
                          {entry.name}
                        </Text>
                      </Group>
                    </UnstyledButton>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">
                      {entry.dir ? '—' : formatBytes(entry.bytes)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">
                      {entry.mtime || '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Tooltip label="删除">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="red"
                        onClick={() => remove(entry)}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                </Table.Tr>
              ))}
          </Table.Tbody>
        </Table>
      </Box>

      <Modal
        opened={!!preview}
        onClose={() => setPreview(null)}
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
    </Stack>
  );
}
