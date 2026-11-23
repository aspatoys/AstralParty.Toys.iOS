import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Badge, Button, Card, Center, Divider, Drawer, Group, Image, List, Loader,
  Pagination, ScrollArea, SimpleGrid, Skeleton, Stack, Text, Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle, IconDownload, IconRefresh, IconShieldCheck,
} from '@tabler/icons-react';
import type { Bridge, MarketItem, MarketState, Task } from '../types';
import { DISCLAIMER } from '../disclaimer';

interface Props {
  bridge: Bridge;
  task: Task;
}

function Cover({ url, name }: { url?: string | null; name: string }) {
  const [broken, setBroken] = useState(false);

  if (!url || broken) {
    return (
      <Center
        h={116}
        style={{
          background: 'var(--mantine-color-default-hover)',
          borderRadius: 'var(--mantine-radius-sm)',
        }}
      >
        <Text size="xl" fw={700} c="dimmed">
          {name.slice(0, 1).toUpperCase()}
        </Text>
      </Center>
    );
  }
  return (
    <Image
      src={url}
      h={116}
      radius="sm"
      fit="cover"
      alt={name}
      onError={() => setBroken(true)}
    />
  );
}

function formatBytes(bytes: number): string {
  if (!bytes) return '–';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

export function Market({ bridge, task }: Props) {
  const [state, setState] = useState<MarketState | null>(null);
  const [consenting, setConsenting] = useState(false);
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    bridge.market_state().then((value) => alive && setState(value));
    return () => {
      alive = false;
    };
  }, [bridge]);

  const list = useQuery({
    queryKey: ['market', 'list', page, state?.baseUrl],
    queryFn: () => bridge.market_list(page),
    enabled: !!state?.accepted,
  });

  const detail = useQuery({
    queryKey: ['market', 'detail', detailId],
    queryFn: () => bridge.market_detail(detailId!),
    enabled: !!detailId && !!state?.accepted,
  });

  const pageCount = useMemo(() => {
    const total = list.data?.total ?? 0;
    const size = list.data?.pageSize ?? 20;
    return size > 0 ? Math.max(1, Math.ceil(total / size)) : 1;
  }, [list.data]);

  const accept = async () => {
    setConsenting(true);
    try {
      const next = await bridge.market_consent(true);
      setState(next);
      notifications.show({ message: '已同意免责声明', color: 'teal' });
    } finally {
      setConsenting(false);
    }
  };

  const install = async (item: MarketItem, version?: string) => {
    const result = await bridge.market_install(item.id, version ?? null);
    if (!result.started) {
      notifications.show({ title: '没能启动安装', message: result.error ?? '', color: 'red' });
    } else {
      notifications.show({ message: `开始安装 ${item.name}`, color: 'blue', autoClose: 1800 });
    }
  };

  if (!state) {
    return (
      <Center mih={260}>
        <Stack align="center" gap="xs">
          <Loader />
          <Text size="sm" c="dimmed">
            正在读取市场设置…
          </Text>
        </Stack>
      </Center>
    );
  }

  if (!state.accepted) {
    return (
      <Card withBorder radius="md" maw={760} mx="auto" padding="lg">
        <Group gap="xs" mb="sm">
          <IconShieldCheck size={20} color="var(--mantine-color-berry-6)" />
          <Text fw={650}>【免责声明 / 风险提示】</Text>
          <Badge size="xs" variant="light" color="gray">
            v{state.requiredVersion}
          </Badge>
        </Group>
        <List size="sm" spacing={6} mb="md">
          {DISCLAIMER.map((line) => (
            <List.Item key={line}>{line}</List.Item>
          ))}
        </List>
        <Alert color="yellow" icon={<IconAlertTriangle />} mb="md">
          同意后才会连接市场（{state.baseUrl}）。未同意时本工具不会发出任何市场请求。
        </Alert>
        <Group justify="flex-end">
          <Button onClick={() => void accept()} loading={consenting} leftSection={<IconShieldCheck size={16} />}>
            我已阅读并同意
          </Button>
        </Group>
      </Card>
    );
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          <Text fw={600}>模组市场</Text>
          <Badge variant="light" color="gray" ff="monospace">
            {state.baseUrl}
          </Badge>
        </Group>
        <Group gap="xs">
          <Text size="sm" c="dimmed">
            {list.data?.total != null ? `${list.data.total} 个模组` : ''}
          </Text>
          <Button
            size="compact-sm"
            variant="default"
            leftSection={<IconRefresh size={14} />}
            onClick={() => void list.refetch()}
            loading={list.isFetching}
          >
            刷新
          </Button>
        </Group>
      </Group>

      {list.data?.ok === false && (
        <Alert color="red" icon={<IconAlertTriangle />} title="市场请求失败">
          {list.data.error}
        </Alert>
      )}

      {list.isLoading ? (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {Array.from({ length: 6 }).map((_, index) => (
            <Card key={index} withBorder padding="md">
              <Skeleton height={116} mb="sm" />
              <Skeleton height={10} width="60%" mb={8} />
              <Skeleton height={8} width="40%" />
            </Card>
          ))}
        </SimpleGrid>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {(list.data?.items ?? []).map((item) => (
            <Card key={item.id} withBorder padding="md" radius="md">
              <Cover url={item.coverUrl} name={item.name} />
              <Group justify="space-between" mt="sm" wrap="nowrap">
                <Text fw={600} size="sm" truncate>
                  {item.name}
                </Text>
                {item.featured && (
                  <Badge size="xs" color="berry" variant="light">
                    推荐
                  </Badge>
                )}
              </Group>
              <Text size="xs" c="dimmed" ff="monospace" truncate>
                {item.id}
              </Text>
              <Text size="xs" c="dimmed" lineClamp={2} mt={4} mih={32}>
                {item.summary || '（无简介）'}
              </Text>
              <Group gap={4} mt="xs" wrap="wrap">
                {item.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag} size="xs" variant="default">
                    {tag}
                  </Badge>
                ))}
                {item.platforms.map((platform) => (
                  <Badge key={platform} size="xs" variant="light" color="gray">
                    {platform}
                  </Badge>
                ))}
              </Group>
              <Group justify="space-between" mt="sm">
                <Text size="xs" c="dimmed">
                  v{item.latestVersion || '?'} · {formatBytes(item.sizeBytes)} · ↓{item.downloads}
                </Text>
                <Group gap={4}>
                  <Button size="compact-xs" variant="default" onClick={() => setDetailId(item.id)}>
                    详情
                  </Button>
                  <Button
                    size="compact-xs"
                    leftSection={<IconDownload size={13} />}
                    onClick={() => void install(item)}
                    disabled={task.running}
                  >
                    安装
                  </Button>
                </Group>
              </Group>
            </Card>
          ))}
        </SimpleGrid>
      )}

      {pageCount > 1 && (
        <Center>
          <Pagination total={pageCount} value={page} onChange={setPage} size="sm" />
        </Center>
      )}

      <Drawer
        opened={!!detailId}
        onClose={() => setDetailId(null)}
        position="right"
        size="lg"
        title={detail.data?.detail?.name ?? detailId ?? '详情'}
      >
        {detail.isLoading ? (
          <Center h={200}>
            <Loader />
          </Center>
        ) : detail.data?.ok === false ? (
          <Alert color="red" icon={<IconAlertTriangle />}>
            {detail.data.error}
          </Alert>
        ) : (
          <Stack gap="sm">
            <Group gap="xs">
              <Text size="xs" c="dimmed" ff="monospace">
                {detail.data?.detail?.id}
              </Text>
              <Badge size="xs" variant="light">
                v{detail.data?.detail?.latestVersion}
              </Badge>
              <Text size="xs" c="dimmed">
                {detail.data?.detail?.author}
              </Text>
            </Group>

            <Text size="sm">{detail.data?.detail?.summary}</Text>
            {detail.data?.detail?.description && (
              <ScrollArea h={180}>
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                  {detail.data.detail.description}
                </Text>
              </ScrollArea>
            )}

            <Divider label="版本" labelPosition="left" />
            <Stack gap="xs">
              {(detail.data?.detail?.versions ?? []).map((version) => (
                <Group key={version.version} justify="space-between" wrap="nowrap">
                  <Group gap="xs" wrap="nowrap">
                    <Badge size="sm" variant="light">
                      {version.version}
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {formatBytes(version.sizeBytes ?? 0)}
                      {version.publishedAt ? ` · ${version.publishedAt.slice(0, 10)}` : ''}
                    </Text>
                  </Group>
                  <Tooltip label={version.changelog || '无更新说明'}>
                    <Button
                      size="compact-xs"
                      leftSection={<IconDownload size={13} />}
                      onClick={() =>
                        detail.data?.detail &&
                        void install(
                          {
                            ...(detail.data.detail as unknown as MarketItem),
                            latestVersion: version.version,
                          },
                          version.version,
                        )
                      }
                      disabled={task.running}
                    >
                      安装
                    </Button>
                  </Tooltip>
                </Group>
              ))}
            </Stack>
          </Stack>
        )}
      </Drawer>
    </Stack>
  );
}
