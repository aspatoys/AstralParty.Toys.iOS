import { Badge, Button, Group, Loader, Menu, Text, Title, Tooltip } from '@mantine/core';
import { IconDownload, IconPlugConnected, IconPower, IconRefresh } from '@tabler/icons-react';
import type { Probe, Task } from '../types';

interface Props {
  probe?: Probe;
  probing: boolean;
  task: Task;
  mock: boolean;
  onRefresh: () => void;
  onInstall: () => void;
  onReconnect: () => void;
  onQuit: () => void;
}

export function Header({
  probe, probing, task, mock, onRefresh, onInstall, onReconnect, onQuit,
}: Props) {
  const device = probe?.device;
  const game = probe?.game;
  const summary = [
    device?.name,
    device?.model,
    device?.ios ? `iOS ${device.ios}` : null,
    game ? `${game.name} ${game.version}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <Group
      h={56}
      px="md"
      justify="space-between"
      wrap="nowrap"
      style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
    >
      <Group gap={10} wrap="nowrap">
        <Title order={4}>AstralParty.Toys</Title>
        <Badge variant="light">iOS</Badge>
        {mock && (
          <Badge color="yellow" variant="light">
            演示数据
          </Badge>
        )}
      </Group>

      <Text size="sm" c="dimmed" truncate style={{ flex: 1, textAlign: 'center' }}>
        {probe ? (probe.connected ? summary : '未连接设备') : '正在探测设备…'}
      </Text>

      <Group gap="xs" wrap="nowrap">
        {task.running && (
          <Group gap={6} wrap="nowrap">
            <Loader size="xs" />
            <Text size="sm" c="dimmed">
              {task.name}…
            </Text>
          </Group>
        )}
        <Tooltip label="重新探测设备">
          <Button variant="default" onClick={onReconnect} loading={probing} px="xs" aria-label="重新探测">
            <IconPlugConnected size={16} />
          </Button>
        </Tooltip>
        <Button
          variant="light"
          leftSection={<IconDownload size={16} />}
          onClick={onInstall}
          loading={task.running && task.name === '安装'}
          disabled={probe?.connected === false || (task.running && task.name !== '安装')}
        >
          一键安装
        </Button>
        <Button
          leftSection={<IconRefresh size={16} />}
          onClick={onRefresh}
          loading={task.running && task.name === '检测'}
          disabled={probe?.connected === false}
        >
          刷新
        </Button>
        <Menu position="bottom-end" withinPortal>
          <Menu.Target>
            <Button variant="subtle" px="xs" aria-label="更多">
              ⋯
            </Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item leftSection={<IconPower size={14} />} onClick={onQuit}>
              退出
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>
    </Group>
  );
}
