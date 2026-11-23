import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Badge, Button, Card, Center, Grid, Group, Loader, Skeleton, Stack, Table, Text,
  TextInput,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle, IconFolderOpen, IconPalette, IconUpload,
} from '@tabler/icons-react';
import type { Bridge, Task } from '../types';

interface Props {
  bridge: Bridge;
  task: Task;
}

export function Custom({ bridge, task }: Props) {
  const skins = useQuery({ queryKey: ['skins'], queryFn: () => bridge.skins() });
  const [zip, setZip] = useState('');
  const [picking, setPicking] = useState(false);
  const [activating, setActivating] = useState<string | null>(null);

  const pick = async () => {
    setPicking(true);
    try {
      const result = await bridge.pick_zip();
      if (result.path) setZip(result.path);
    } finally {
      setPicking(false);
    }
  };

  const doImport = async () => {
    const result = await bridge.skins_import(zip.trim() || null);
    if (!result.started) {
      notifications.show({ title: '没能启动导入', message: result.error ?? '', color: 'red' });
    } else {
      notifications.show({ message: '开始导入卡面…', color: 'blue', autoClose: 1600 });
    }
  };

  const activate = async (name: string) => {
    setActivating(name);
    try {
      const result = await bridge.skins_activate(name);
      if (result.error) {
        notifications.show({ title: '启用失败', message: result.error, color: 'red' });
        return;
      }
      notifications.show({ message: `卡面方案已切到 ${name}`, color: 'teal' });
      void skins.refetch();
    } finally {
      setActivating(null);
    }
  };

  return (
    <Stack gap="md">
      <Card withBorder padding="md" radius="md">
        <Group gap="xs" mb={4}>
          <IconPalette size={18} />
          <Text fw={600}>卡面</Text>
          <Badge size="xs" variant="light" color="gray">
            skins/
          </Badge>
        </Group>
        <Text size="sm" c="dimmed">
          卡面方案就是一个目录：<code>skins/&lt;方案名&gt;/UT_HandCard_&lt;卡牌ID&gt;.png</code>。
          ZIP 里应当只有一个顶层目录，导入后目录名就是方案名。
        </Text>

        <Group mt="md" gap="xs" wrap="nowrap">
          <TextInput
            flex={1}
            placeholder="卡面方案 ZIP 路径"
            value={zip}
            onChange={(event) => setZip(event.currentTarget.value)}
            leftSection={<IconFolderOpen size={15} />}
          />
          <Button variant="default" onClick={() => void pick()} loading={picking}>
            选择…
          </Button>
          <Button
            leftSection={<IconUpload size={16} />}
            onClick={() => void doImport()}
            loading={task.running && task.name === '导入卡面'}
            disabled={!zip.trim()}
          >
            导入
          </Button>
        </Group>
      </Card>

      <Card withBorder padding="md" radius="md">
        <Group justify="space-between" mb="sm">
          <Text fw={600}>已安装的方案</Text>
          <Button
            size="compact-sm"
            variant="default"
            onClick={() => void skins.refetch()}
            loading={skins.isFetching}
          >
            刷新
          </Button>
        </Group>

        {skins.data?.error && (
          <Alert color="red" icon={<IconAlertTriangle />} mb="sm">
            {skins.data.error}
          </Alert>
        )}

        <Table striped highlightOnHover verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>方案</Table.Th>
              <Table.Th w={110}>卡面数</Table.Th>
              <Table.Th w={110}>文件数</Table.Th>
              <Table.Th w={110}>操作</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {skins.isLoading &&
              Array.from({ length: 3 }).map((_, index) => (
                <Table.Tr key={index}>
                  <Table.Td><Skeleton height={10} width="50%" /></Table.Td>
                  <Table.Td><Skeleton height={8} width={40} /></Table.Td>
                  <Table.Td><Skeleton height={8} width={40} /></Table.Td>
                  <Table.Td><Skeleton height={22} width={60} radius="sm" /></Table.Td>
                </Table.Tr>
              ))}

            {!skins.isLoading && (skins.data?.skins ?? []).length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={4}>
                  <Center mih={90}>
                    <Text size="sm" c="dimmed">
                      还没有卡面方案
                    </Text>
                  </Center>
                </Table.Td>
              </Table.Tr>
            )}

            {!skins.isLoading &&
              (skins.data?.skins ?? []).map((skin) => (
                <Table.Tr key={skin.name}>
                  <Table.Td>
                    <Text size="sm" ff="monospace">
                      {skin.name}
                    </Text>
                    <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                      {skin.path}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light">{skin.cards}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{skin.files}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Button
                      size="compact-xs"
                      variant="light"
                      onClick={() => void activate(skin.name)}
                      loading={activating === skin.name}
                      disabled={task.running && activating === null}
                    >
                      启用
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
          </Table.Tbody>
        </Table>

        <Text size="xs" c="dimmed" mt="sm">
          「启用」写的是 <code>mods/CardSkinMod/config.json</code> 里的 <code>ActiveSkin</code>
          （文本定点替换，保留注释）。改完在游戏里切一次场景或重开即可生效。
        </Text>
      </Card>
    </Stack>
  );
}
