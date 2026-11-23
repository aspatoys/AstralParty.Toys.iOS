import { useEffect, useMemo, useState } from 'react';
import {
  Badge, Button, Center, Group, Loader, Modal, ScrollArea, Skeleton, Stack, Switch,
  Table, Text, Textarea, TextInput, Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconEdit, IconSearch } from '@tabler/icons-react';
import type { Bridge, ModInfo } from '../types';

interface Props {
  bridge: Bridge;
  mods: ModInfo[];
  loading: boolean;
  taskRunning: boolean;
  pendingMod: string | null;
  setPendingMod: (id: string | null) => void;
  onChanged: () => void;
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, index) => (
        <Table.Tr key={index}>
          <Table.Td><Skeleton height={18} width={36} radius="xl" /></Table.Td>
          <Table.Td>
            <Skeleton height={10} width="60%" mb={6} />
            <Skeleton height={8} width="35%" />
          </Table.Td>
          <Table.Td><Skeleton height={8} width={40} /></Table.Td>
          <Table.Td><Skeleton height={8} width={70} /></Table.Td>
          <Table.Td><Skeleton height={16} width={90} radius="sm" /></Table.Td>
          <Table.Td><Skeleton height={22} width={52} radius="sm" /></Table.Td>
        </Table.Tr>
      ))}
    </>
  );
}

export function Mods({
  bridge, mods, loading, taskRunning, pendingMod, setPendingMod, onChanged,
}: Props) {
  const [filter, setFilter] = useState('');
  const [onlyEnabled, setOnlyEnabled] = useState(false);
  const [configFor, setConfigFor] = useState<ModInfo | null>(null);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return mods.filter((mod) => {
      if (onlyEnabled && !mod.enabled) return false;
      if (!needle) return true;
      const sidecar = mod.sidecar ?? {};
      return `${mod.id} ${sidecar.name ?? ''} ${sidecar.author ?? ''}`
        .toLowerCase()
        .includes(needle);
    });
  }, [mods, filter, onlyEnabled]);

  const toggle = async (mod: ModInfo, next: boolean) => {
    setPendingMod(mod.id);
    try {
      const result = await bridge.set_mod_enabled(mod.id, next);
      if (!result.started) {
        setPendingMod(null);
        notifications.show({
          title: '没能启动',
          message: result.error ?? '',
          color: 'red',
        });
      }
    } catch (error) {
      setPendingMod(null);
      notifications.show({ title: '操作失败', message: String(error), color: 'red' });
    }
  };

  const busy = taskRunning || pendingMod !== null;

  return (
    <Stack gap="sm">
      <Group gap="md" wrap="wrap">
        <TextInput
          flex={1}
          miw={220}
          placeholder="筛选模组（名称 / ID / 作者）"
          leftSection={<IconSearch size={15} />}
          value={filter}
          onChange={(event) => setFilter(event.currentTarget.value)}
        />
        <Switch
          label="只看启用"
          checked={onlyEnabled}
          onChange={(event) => setOnlyEnabled(event.currentTarget.checked)}
        />
        <Text size="sm" c="dimmed">
          {loading ? '读取中…' : `${visible.length} / ${mods.length} 个模组`}
        </Text>
      </Group>

      <Table.ScrollContainer minWidth={820}>
        <Table striped highlightOnHover verticalSpacing="xs" stickyHeader>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={72}>启用</Table.Th>
              <Table.Th>模组</Table.Th>
              <Table.Th w={84}>版本</Table.Th>
              <Table.Th w={150}>作者</Table.Th>
              <Table.Th w={150}>平台</Table.Th>
              <Table.Th w={84}>配置</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {loading && <SkeletonRows />}

            {!loading && visible.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={6}>
                  <Center mih={120}>
                    <Text c="dimmed">
                      {mods.length === 0 ? '还没有读到模组 —— 点右上角「刷新」' : '没有匹配的模组'}
                    </Text>
                  </Center>
                </Table.Td>
              </Table.Tr>
            )}

            {!loading &&
              visible.map((mod) => {
                const sidecar = mod.sidecar ?? {};
                const pending = pendingMod === mod.id;
                return (
                  <Table.Tr key={mod.id} style={{ opacity: mod.enabled ? 1 : 0.55 }}>
                    <Table.Td>
                      <Group gap={6} wrap="nowrap">
                        <Switch
                          size="sm"
                          checked={mod.enabled}
                          disabled={busy && !pending}
                          onChange={(event) => void toggle(mod, event.currentTarget.checked)}
                          aria-label={`${mod.enabled ? '停用' : '启用'} ${mod.id}`}
                        />
                        {pending && <Loader size={12} />}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={550}>
                        {sidecar.name ?? mod.id}
                      </Text>
                      <Text size="xs" c="dimmed" ff="monospace">
                        {mod.id}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{sidecar.version ?? '–'}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" truncate>
                        {sidecar.author ?? '–'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="wrap">
                        {(sidecar.platforms ?? []).map((platform) => (
                          <Badge key={platform} size="xs" variant="default">
                            {platform}
                          </Badge>
                        ))}
                        {(sidecar.platforms ?? []).length === 0 && (
                          <Text size="xs" c="dimmed">–</Text>
                        )}
                        {sidecar._parse_error && (
                          <Tooltip label={sidecar._parse_error}>
                            <IconAlertCircle size={14} color="var(--mantine-color-yellow-6)" />
                          </Tooltip>
                        )}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Button
                        size="compact-xs"
                        variant="light"
                        leftSection={<IconEdit size={13} />}
                        disabled={!mod.has_config || busy}
                        onClick={() => setConfigFor(mod)}
                      >
                        编辑
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      {configFor && (
        <ConfigModal
          bridge={bridge}
          mod={configFor}
          onClose={() => setConfigFor(null)}
          onSaved={() => {
            onChanged();
          }}
        />
      )}
    </Stack>
  );
}

/* ------------------------------------------------------------------ 配置编辑 */

interface ConfigProps {
  bridge: Bridge;
  mod: ModInfo;
  onClose: () => void;
  onSaved: () => void;
}

function ConfigModal({ bridge, mod, onClose, onSaved }: ConfigProps) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setStatus(null);

    bridge
      .read_config(mod.id, mod.dir)
      .then((result) => {
        if (!alive) return;
        if (result.error) {
          setError(result.error);
          return;
        }
        setText(result.text ?? '{\n  \n}');
        setStatus(result.exists ? (result.path ?? null) : '该模组还没有 config.json，保存会新建一份');
      })
      .catch((cause) => alive && setError(String(cause)))
      .finally(() => alive && setLoading(false));

    return () => {
      alive = false;
    };
  }, [bridge, mod.id, mod.dir]);

  const save = async () => {
    setError(null);
    setStatus(null);
    try {
      const parsed = JSON.parse(text);
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
        setError('顶层必须是 JSON 对象');
        return;
      }
    } catch (cause) {
      setError(`JSON 解析失败：${(cause as Error).message}`);
      return;
    }

    setSaving(true);
    try {
      const result = await bridge.write_config(mod.id, text, mod.dir);
      if (result.error) {
        setError(result.error);
        return;
      }
      setStatus(`已保存 ${result.bytes ?? 0} B`);
      onSaved();
      notifications.show({ message: `${mod.id} 配置已保存`, color: 'teal', autoClose: 1800 });
      setTimeout(onClose, 500);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      opened
      onClose={onClose}
      size="xl"
      title={
        <Text ff="monospace" size="sm">
          {mod.id}/config.json
        </Text>
      }
      styles={{ body: { paddingTop: 8 } }}
    >
      {loading ? (
        <Stack gap="xs" h={360}>
          <Center h="100%">
            <Stack align="center" gap="xs">
              <Loader />
              <Text size="sm" c="dimmed">
                正在读取配置…
              </Text>
            </Stack>
          </Center>
        </Stack>
      ) : (
        <Stack gap="xs">
          <ScrollArea h={380} type="auto">
            <Textarea
              value={text}
              onChange={(event) => setText(event.currentTarget.value)}
              autosize
              minRows={18}
              maxRows={24}
              styles={{
                input: { fontFamily: 'var(--mantine-font-family-monospace)', fontSize: 12.5 },
              }}
              spellCheck={false}
            />
          </ScrollArea>
          <Group justify="space-between" wrap="nowrap">
            <Text size="xs" c={error ? 'red' : 'dimmed'} style={{ wordBreak: 'break-all' }}>
              {error ?? status ?? ''}
            </Text>
            <Group gap="xs" wrap="nowrap">
              <Button variant="default" onClick={onClose} disabled={saving}>
                取消
              </Button>
              <Button onClick={() => void save()} loading={saving}>
                保存
              </Button>
            </Group>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
