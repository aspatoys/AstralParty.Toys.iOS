import { Badge, Box, Button, Group, Loader, Menu, Text, Tooltip } from '@mantine/core';
import { IconDownload, IconPlugConnected, IconPower, IconRefresh } from '@tabler/icons-react';
import type { Probe, Task } from '../types';
import { Glass } from '../ui/Glass';

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
    <Glass
      radius={0}
      padding="6px 16px"
      className="ios-hairline-bottom"
      style={{ width: '100%', position: 'relative', zIndex: 20 }}
    >
      <Group h={44} justify="space-between" wrap="nowrap">
        <Group gap={8} wrap="nowrap">
          <Box
            w={10}
            h={10}
            style={{
              borderRadius: 999,
              background: 'linear-gradient(135deg, #ff375f, #bf5af2)',
              boxShadow: '0 0 10px rgba(191, 90, 242, 0.55)',
            }}
          />
          <Text fw={600} size="sm" style={{ letterSpacing: 0.2 }}>
            AstralParty.Toys
          </Text>
          <Badge size="xs" variant="light" color="iosgray">
            iOS
          </Badge>
          {mock && (
            <Badge size="xs" color="yellow" variant="light">
              演示数据
            </Badge>
          )}
        </Group>

        <Text size="xs" c="dimmed" truncate style={{ flex: 1, textAlign: 'center' }}>
          {probe ? (probe.connected ? summary : '未连接设备') : '正在探测设备…'}
        </Text>

        <Group gap={6} wrap="nowrap">
          {task.running && (
            <Group gap={6} wrap="nowrap">
              <Loader size={12} />
              <Text size="xs" c="dimmed">
                {task.name}…
              </Text>
            </Group>
          )}
          <Tooltip label="重新探测设备">
            <Button
              variant="subtle"
              color="iosgray"
              onClick={onReconnect}
              loading={probing}
              px={8}
              aria-label="重新探测"
            >
              <IconPlugConnected size={16} />
            </Button>
          </Tooltip>
          <Button
            variant="light"
            leftSection={<IconDownload size={15} />}
            onClick={onInstall}
            loading={task.running && task.name === '安装'}
            disabled={probe?.connected === false || (task.running && task.name !== '安装')}
            size="compact-sm"
          >
            一键安装
          </Button>
          <Button
            leftSection={<IconRefresh size={15} />}
            onClick={onRefresh}
            loading={task.running && task.name === '检测'}
            disabled={probe?.connected === false}
            size="compact-sm"
          >
            刷新
          </Button>
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <Button variant="subtle" color="iosgray" px={8} aria-label="更多">
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
    </Glass>
  );
}
