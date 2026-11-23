import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Center, Group, Loader, NavLink, Stack, Text,
} from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle, IconBox, IconFolder, IconList, IconPalette, IconSettings,
  IconShoppingCart,
} from '@tabler/icons-react';

import { getBridge, isMock } from './api';
import type { Bridge, Task } from './types';
import { Header } from './components/Header';
import { Overview } from './components/Overview';
import { Mods } from './components/Mods';
import { Market } from './components/Market';
import { Custom } from './components/Custom';
import { Files } from './components/Files';
import { Settings } from './components/Settings';
import { Output } from './components/Output';

const IDLE: Task = { name: null, running: false, ok: null, error: null };

const PAGES = [
  { key: 'overview', label: '概览', icon: IconBox },
  { key: 'mods', label: '模组', icon: IconList },
  { key: 'market', label: '市场', icon: IconShoppingCart },
  { key: 'custom', label: '自定义', icon: IconPalette },
  { key: 'files', label: '文件', icon: IconFolder },
  { key: 'settings', label: '设置', icon: IconSettings },
] as const;

type PageKey = (typeof PAGES)[number]['key'];

export default function App() {
  const [bridge, setBridge] = useState<Bridge | null>(null);
  const [bridgeError, setBridgeError] = useState<string | null>(null);
  const [page, setPage] = useState<PageKey>('overview');
  const [task, setTask] = useState<Task>(IDLE);
  const [lines, setLines] = useState<string[]>([]);
  const [pendingMod, setPendingMod] = useState<string | null>(null);

  const lastTask = useRef<Task | null>(null);
  const autoRefreshed = useRef(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    getBridge()
      .then(setBridge)
      .catch((error) => setBridgeError(String(error)));
  }, []);

  // 任务状态与日志流：每 400ms 拉一次 drain()
  useEffect(() => {
    if (!bridge) return;
    let alive = true;

    const tick = async () => {
      try {
        const state = await bridge.drain();
        if (!alive) return;
        if (state.lines.length) {
          setLines((prev) => [...prev, ...state.lines].slice(-1500));
        }
        const previous = lastTask.current;
        if (previous?.running && !state.task.running) {
          setPendingMod(null);
          void queryClient.invalidateQueries();
          if (state.task.ok) {
            notifications.show({ message: `${state.task.name} 完成`, color: 'teal', autoClose: 2000 });
          } else {
            notifications.show({
              title: `${state.task.name} 失败`,
              message: state.task.error ?? '',
              color: 'red',
              autoClose: 6000,
            });
          }
        }
        lastTask.current = state.task;
        setTask(state.task);
      } catch {
        /* 关闭窗口时会话会断，忽略 */
      }
    };

    const timer = window.setInterval(tick, 400);
    void tick();
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [bridge, queryClient]);

  const probe = useQuery({
    queryKey: ['probe'],
    queryFn: () => bridge!.probe(),
    enabled: !!bridge,
    refetchInterval: 20000,
  });

  const connected = probe.data?.connected === true;

  const report = useQuery({
    queryKey: ['report'],
    queryFn: () => bridge!.get_report(),
    enabled: !!bridge && connected,
  });

  const mods = useQuery({
    queryKey: ['mods'],
    queryFn: () => bridge!.get_mods(),
    enabled: !!bridge && connected,
  });

  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: () => bridge!.settings(),
    enabled: !!bridge,
  });

  useEffect(() => {
    if (!bridge || autoRefreshed.current || !connected) return;
    autoRefreshed.current = true;
    void bridge.refresh();
  }, [bridge, connected]);

  const startRefresh = useCallback(() => {
    if (!bridge) return;
    void bridge.refresh().then((result) => {
      if (!result.started) {
        notifications.show({ title: '没能启动检测', message: result.error ?? '', color: 'red' });
      }
    });
  }, [bridge]);

  // 一键安装：载荷取默认目录，注入 + 投放一起做
  const quickInstall = useCallback(() => {
    if (!bridge) return;
    void bridge.install(null, true, true).then((result) => {
      if (!result.started) {
        notifications.show({ title: '没能启动安装', message: result.error ?? '', color: 'red' });
      }
    });
  }, [bridge]);

  if (bridgeError) {
    return (
      <Center h="100vh" p="xl">
        <Alert color="red" title="界面桥连接失败" icon={<IconAlertTriangle />}>
          {bridgeError}
        </Alert>
      </Center>
    );
  }

  if (!bridge) {
    return (
      <Center h="100vh">
        <Stack align="center" gap="xs">
          <Loader size="lg" />
          <Text c="dimmed">正在连接界面桥…</Text>
        </Stack>
      </Center>
    );
  }

  return (
    <Group h="100vh" gap={0} align="stretch" wrap="nowrap">
      <Box
        w={212}
        style={{
          borderRight: '1px solid var(--mantine-color-default-border)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Stack gap={2} p="xs" style={{ flex: 1 }}>
          {PAGES.map((item) => (
            <NavLink
              key={item.key}
              active={page === item.key}
              onClick={() => setPage(item.key)}
              label={item.label}
              leftSection={<item.icon size={17} />}
              variant="light"
              style={{ borderRadius: 'var(--mantine-radius-md)' }}
            />
          ))}
        </Stack>
        <Text size="10px" c="dimmed" ta="center" pb={8}>
          v{settings.data?.appVersion ?? '–'}
          {isMock(bridge) ? ' · 演示数据' : ''}
        </Text>
      </Box>

      <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
        <Header
          probe={probe.data}
          probing={probe.isFetching}
          task={task}
          mock={isMock(bridge)}
          onRefresh={startRefresh}
          onInstall={quickInstall}
          onReconnect={() => {
            void bridge.disconnect();
            void probe.refetch();
          }}
          onQuit={() => void bridge.quit()}
        />

        {probe.data && !probe.data.connected && (
          <Alert color="yellow" icon={<IconAlertTriangle />} mx="md" mt="xs" title="未连接设备">
            {probe.data.error ?? '用 USB 连接设备，并在设备上点「信任此电脑」。'}
          </Alert>
        )}

        <Box style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {page === 'overview' && (
            <Overview
              report={report.data ?? null}
              loading={report.isFetching && !report.data}
              taskRunning={task.running}
              onRefresh={startRefresh}
            />
          )}

          {page === 'mods' && (
            <Mods
              bridge={bridge}
              mods={mods.data ?? []}
              loading={mods.isFetching && !mods.data}
              taskRunning={task.running}
              pendingMod={pendingMod}
              setPendingMod={setPendingMod}
              onChanged={() => void queryClient.invalidateQueries({ queryKey: ['mods'] })}
            />
          )}

          {page === 'market' && <Market bridge={bridge} task={task} />}

          {page === 'custom' && <Custom bridge={bridge} task={task} />}

          {page === 'files' && <Files bridge={bridge} enabled={connected} />}

          {page === 'settings' && (
            <Settings
              bridge={bridge}
              task={task}
              settings={settings.data}
              onChanged={() => void queryClient.invalidateQueries()}
            />
          )}
        </Box>

        <Output lines={lines} task={task} onClear={() => setLines([])} />
      </Stack>
    </Group>
  );
}
