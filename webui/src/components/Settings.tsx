import { useEffect, useState } from 'react';
import {
  Alert, Badge, Button, Card, Code, Divider, Group, List, Modal, Stack, Text, TextInput,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle, IconArrowBackUp, IconCloudDownload, IconDownload, IconFolderOpen,
  IconShieldCheck, IconTrash,
} from '@tabler/icons-react';
import type { Bridge, MarketState, SettingsResult, Task } from '../types';
import { DISCLAIMER } from '../disclaimer';

interface Props {
  bridge: Bridge;
  task: Task;
  settings?: SettingsResult;
  onChanged: () => void;
}

export function Settings({ bridge, task, settings, onChanged }: Props) {
  const [baseUrl, setBaseUrl] = useState('');
  const [consent, setConsent] = useState<MarketState | null>(null);
  const [savingBase, setSavingBase] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [accepting, setAccepting] = useState(false);

  const [payload, setPayload] = useState('');
  const [patch, setPatch] = useState(true);
  const [deploy, setDeploy] = useState(true);
  const [picking, setPicking] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setBaseUrl(settings.market.baseUrl);
    setConsent(settings.market);
    setPayload(settings.payloadDefault);
  }, [settings]);

  const saveBase = async () => {
    setSavingBase(true);
    try {
      const result = await bridge.set_market_base(baseUrl.trim());
      if (result.error) {
        notifications.show({ title: '保存失败', message: result.error, color: 'red' });
        return;
      }
      notifications.show({ message: '市场地址已保存', color: 'teal' });
      onChanged();
    } finally {
      setSavingBase(false);
    }
  };

  const withdraw = async () => {
    const next = await bridge.market_consent(false);
    setConsent(next);
    notifications.show({ message: '已撤回同意，市场已关闭', color: 'yellow' });
    onChanged();
  };

  const accept = async () => {
    setAccepting(true);
    try {
      const next = await bridge.market_consent(true);
      setConsent(next);
      setNoticeOpen(false);
      notifications.show({ message: '已同意免责声明', color: 'teal' });
      onChanged();
    } finally {
      setAccepting(false);
    }
  };

  const pickPayload = async () => {
    setPicking(true);
    try {
      const result = await bridge.pick_folder();
      if (result.path) setPayload(result.path);
    } finally {
      setPicking(false);
    }
  };

  const install = async () => {
    if (!patch && !deploy) {
      notifications.show({ title: '至少勾选一项', message: '', color: 'yellow' });
      return;
    }
    const result = await bridge.install(payload.trim() || null, patch, deploy);
    if (!result.started) {
      notifications.show({ title: '没能启动安装', message: result.error ?? '', color: 'red' });
    }
  };

  const confirmRestore = (removeLoader: boolean) =>
    modals.openConfirmModal({
      title: removeLoader ? '完全卸载' : '还原代码包',
      children: (
        <Text size="sm">
          {removeLoader
            ? '还原代码包并删除 Documents/CesiumLoader 整个目录？'
            : '用 backups/ 里的原始包还原代码包？游戏需要完全退出。'}
        </Text>
      ),
      labels: { confirm: '确认', cancel: '取消' },
      confirmProps: removeLoader ? { color: 'red' } : undefined,
      onConfirm: async () => {
        const result = await bridge.restore(removeLoader);
        if (!result.started) {
          notifications.show({ title: '没能启动', message: result.error ?? '', color: 'red' });
        }
        onChanged();
      },
    });

  const pullLoader = async () => {
    const result = await bridge.pull_loader(true, false, payload.trim() || null);
    if (!result.started) {
      notifications.show({ title: '没能启动拉取', message: result.error ?? '', color: 'red' });
      return;
    }
    notifications.show({ message: '正在拉取最新 CesiumLoader，进度见底部输出', color: 'blue', autoClose: 2400 });
  };

  const installing = task.running && task.name === '安装';
  const pulling = task.running && task.name === '拉取最新 CesiumLoader';

  return (
    <Stack gap="md" maw={880}>
      <Card withBorder padding="md" radius="md">
        <Group justify="space-between">
          <Text fw={600}>市场</Text>
          {consent?.accepted ? (
            <Badge color="teal" variant="light">
              已同意 v{consent.requiredVersion}
            </Badge>
          ) : (
            <Badge color="yellow" variant="light">
              未同意
            </Badge>
          )}
        </Group>
        <Text size="sm" c="dimmed" mt={4}>
          未同意免责声明时，本工具不会向市场发出任何请求。
        </Text>

        <Group mt="md" gap="xs" wrap="nowrap">
          <TextInput
            flex={1}
            label="市场地址"
            placeholder="https://forge.hiynet.com"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.currentTarget.value)}
          />
          <Button variant="default" mt={22} onClick={() => void saveBase()} loading={savingBase}>
            保存
          </Button>
        </Group>

        <Divider my="md" />

        {consent?.accepted ? (
          <Button color="yellow" variant="light" onClick={() => void withdraw()}>
            撤回同意（关闭市场）
          </Button>
        ) : (
          <Button leftSection={<IconShieldCheck size={16} />} onClick={() => setNoticeOpen(true)}>
            查看并同意免责声明
          </Button>
        )}
      </Card>

      <Card withBorder padding="md" radius="md">
        <Text fw={600}>维护</Text>
        <Text size="sm" c="dimmed" mt={4}>
          <b>注入代码包</b>：改写容器里那份热更代码包，让游戏启动时加载引导。
          <br />
          <b>投放载荷</b>：把 <code>CesiumLoader.Android.Bootstrap.dll</code>、<code>sdk/</code>、
          <code>mods/</code> 写进 <code>Documents/CesiumLoader/</code>。
        </Text>

        <Group mt="md" gap="xs" wrap="nowrap">
          <TextInput
            flex={1}
            placeholder="载荷目录（payload/CesiumLoader）"
            value={payload}
            onChange={(event) => setPayload(event.currentTarget.value)}
            leftSection={<IconFolderOpen size={15} />}
          />
          <Button variant="default" onClick={() => void pickPayload()} loading={picking}>
            选择…
          </Button>
        </Group>

        <Group mt="xs" gap="sm" wrap="nowrap" align="center">
          <Button
            variant="light"
            leftSection={<IconCloudDownload size={16} />}
            loading={pulling}
            onClick={() => void pullLoader()}
          >
            拉取最新 CesiumLoader
          </Button>
          <Text size="xs" c="dimmed">
            从官方 Release 取 SDK 与全部模组，引导 DLL 从安卓包取；下载缓存在 work/release/，
            不会覆盖载荷里已有的配置与额外文件
          </Text>
        </Group>

        <Group mt="md" gap="lg">
          <Button.Group>
            <Button
              variant={patch ? 'light' : 'default'}
              onClick={() => setPatch((value) => !value)}
              size="compact-md"
            >
              {patch ? '✓ ' : ''}注入代码包
            </Button>
            <Button
              variant={deploy ? 'light' : 'default'}
              onClick={() => setDeploy((value) => !value)}
              size="compact-md"
            >
              {deploy ? '✓ ' : ''}投放载荷
            </Button>
          </Button.Group>
          <Button leftSection={<IconDownload size={16} />} onClick={() => void install()} loading={installing}>
            开始安装
          </Button>
        </Group>

        <Divider my="md" />

        <Group gap="sm">
          <Button
            variant="default"
            leftSection={<IconArrowBackUp size={16} />}
            onClick={() => confirmRestore(false)}
            loading={task.running && task.name === '还原代码包'}
            disabled={installing}
          >
            仅还原代码包
          </Button>
          <Button
            color="red"
            variant="light"
            leftSection={<IconTrash size={16} />}
            onClick={() => confirmRestore(true)}
            loading={task.running && task.name === '完全卸载'}
            disabled={installing}
          >
            完全卸载
          </Button>
        </Group>
      </Card>

      <Card withBorder padding="md" radius="md">
        <Text fw={600} mb={6}>
          关于
        </Text>
        <Stack gap={4}>
          <Group gap="xs">
            <Text size="sm" c="dimmed">版本</Text>
            <Text size="sm">{settings?.appVersion ?? '–'}</Text>
          </Group>
          <Group gap="xs">
            <Text size="sm" c="dimmed">仓库</Text>
            <Code>github.com/aspatoys/AstralParty.Toys.iOS</Code>
          </Group>
          <Group gap="xs">
            <Text size="sm" c="dimmed">许可</Text>
            <Text size="sm">AGPL-3.0</Text>
          </Group>
        </Stack>
      </Card>

      <Modal opened={noticeOpen} onClose={() => setNoticeOpen(false)} title="【免责声明 / 风险提示】" size="lg">
        <List size="sm" spacing={6}>
          {DISCLAIMER.map((line) => (
            <List.Item key={line}>{line}</List.Item>
          ))}
        </List>
        <Alert color="yellow" icon={<IconAlertTriangle />} mt="md">
          同意后才会连接市场。
        </Alert>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setNoticeOpen(false)} disabled={accepting}>
            取消
          </Button>
          <Button onClick={() => void accept()} loading={accepting}>
            我已阅读并同意
          </Button>
        </Group>
      </Modal>
    </Stack>
  );
}
