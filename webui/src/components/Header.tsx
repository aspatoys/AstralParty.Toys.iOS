import { Badge, Button, Divider, Group, Loader, Menu, Text, Title, Tooltip } from '@mantine/core';
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
  // DeviceName 是用户给设备起的名字，不是机型；机型是 ProductType（例如 iPhone18,3）
  const model = device?.model ?? '未知机型';
  const deviceName = device?.name ?? '—';
  const facts = [
    device?.ios ? `iOS ${device.ios}` : null,
    game ? `${game.name} ${game.version}` : (probe?.error ?? null),
  ].filter(Boolean) as string[];

  return (
    <Group
      h={56}
      px="md"
      justify="space-between"
      wrap="nowrap"
      style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
    >
      <Group gap={10} wrap="nowrap" style={{ flex: '0 0 auto' }}>
        <Title order={4}>AstralParty.Toys</Title>
        <Badge variant="light">iOS</Badge>
        {mock && (
          <Badge color="yellow" variant="light">
            演示数据
          </Badge>
        )}
      </Group>

      <Divider orientation="vertical" />

      <Group gap={8} wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
        {probe?.connected ? (
          <>
            <Badge
              variant="default"
              ff="monospace"
              style={{ flex: '0 0 auto', cursor: 'default' }}
            >
              {model}
            </Badge>
            <Tooltip label={deviceName} withArrow openDelay={400}>
              <Text size="sm" fw={500} truncate style={{ minWidth: 0, flex: '0 1 auto' }}>
                {deviceName}
              </Text>
            </Tooltip>
            <Text size="sm" c="dimmed" truncate style={{ minWidth: 0, flex: '1 1 auto' }}>
              {facts.join(' · ')}
            </Text>
          </>
        ) : (
          <Text size="sm" c="dimmed" truncate>
            {probe ? '未连接设备' : '正在探测设备…'}
          </Text>
        )}
      </Group>

      <Group gap="xs" wrap="nowrap" style={{ flex: '0 0 auto' }}>
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
