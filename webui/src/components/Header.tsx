import { Badge, Box, Button, Divider, Group, Loader, Menu, Text, Tooltip } from '@mantine/core';
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

  // DeviceName 是用户给设备起的名字，不是机型；机型是 ProductType（例如 iPhone18,3）
  const model = device?.model ?? '未知机型';
  const deviceName = device?.name ?? '—';
  const facts = [
    device?.ios ? `iOS ${device.ios}` : null,
    game ? `${game.name} ${game.version}` : (probe?.error ?? null),
  ].filter(Boolean) as string[];

  return (
    <Glass
      radius={0}
      padding="6px 16px"
      className="ios-hairline-bottom"
      style={{ width: '100%', position: 'relative', zIndex: 20 }}
    >
      <Group h={44} justify="space-between" wrap="nowrap" gap="md">
        {/* 左：品牌 + 设备信息（信息靠左，不做居中，避免被右侧按钮挤偏） */}
        <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
          <Box
            w={10}
            h={10}
            style={{
              borderRadius: 999,
              flex: '0 0 auto',
              background: 'linear-gradient(135deg, #ff375f, #bf5af2)',
              boxShadow: '0 0 10px rgba(191, 90, 242, 0.55)',
            }}
          />
          <Text fw={600} size="sm" style={{ letterSpacing: 0.2, flex: '0 0 auto' }}>
            AstralParty.Toys
          </Text>
          <Badge size="xs" variant="light" color="iosgray" style={{ flex: '0 0 auto' }}>
            iOS
          </Badge>
          {mock && (
            <Badge size="xs" color="yellow" variant="light" style={{ flex: '0 0 auto' }}>
              演示数据
            </Badge>
          )}

          <Divider orientation="vertical" mx={4} style={{ flex: '0 0 auto', height: 18 }} />

          {probe?.connected ? (
            <>
              <Tooltip label={`设备名：${deviceName}`} withArrow>
                <Badge
                  size="sm"
                  variant="default"
                  ff="monospace"
                  style={{ flex: '0 0 auto', cursor: 'default' }}
                >
                  {model}
                </Badge>
              </Tooltip>
              <Text size="xs" c="dimmed" truncate style={{ minWidth: 0 }}>
                {facts.join(' · ')}
              </Text>
            </>
          ) : (
            <Text size="xs" c="dimmed" truncate>
              {probe ? '未连接设备' : '正在探测设备…'}
            </Text>
          )}
        </Group>

        {/* 右：动作 */}
        <Group gap={6} wrap="nowrap" style={{ flex: '0 0 auto' }}>
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
