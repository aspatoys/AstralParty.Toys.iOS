import type { ReactNode } from 'react';
import {
  Alert, Badge, Button, Card, Center, Code, Group, SimpleGrid, Skeleton, Stack, Text,
} from '@mantine/core';
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react';
import type { PatchState, Report } from '../types';

const PATCH: Record<PatchState, { label: string; color: string }> = {
  patched: { label: '已注入', color: 'teal' },
  'patched-external': { label: '已注入（外部安装）', color: 'teal' },
  clean: { label: '未注入', color: 'yellow' },
  unknown: { label: '未知', color: 'red' },
};

interface FieldProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
}

function Field({ label, value, mono = true }: FieldProps) {
  return (
    <Group justify="space-between" gap="sm" wrap="nowrap" align="flex-start">
      <Text size="xs" c="dimmed" style={{ flex: '0 0 auto' }}>
        {label}
      </Text>
      <Text
        size="xs"
        ff={mono ? 'monospace' : undefined}
        ta="right"
        style={{ wordBreak: 'break-all' }}
      >
        {value}
      </Text>
    </Group>
  );
}

function CardBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card withBorder padding="md" radius="md">
      <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={8}>
        {title}
      </Text>
      {children}
    </Card>
  );
}

function SkeletonGrid() {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
      {Array.from({ length: 6 }).map((_, index) => (
        <Card key={index} withBorder padding="md">
          <Skeleton height={10} width="40%" mb={12} />
          <Skeleton height={8} mb={8} />
          <Skeleton height={8} mb={8} />
          <Skeleton height={8} width="70%" />
        </Card>
      ))}
    </SimpleGrid>
  );
}

interface Props {
  report: Report | null;
  loading: boolean;
  taskRunning: boolean;
  onRefresh: () => void;
}

export function Overview({ report, loading, taskRunning, onRefresh }: Props) {
  if (loading) return <SkeletonGrid />;

  if (!report) {
    return (
      <Center mih={260}>
        <Stack align="center" gap="sm">
          <Text c="dimmed">还没有检测结果</Text>
          <Button
            leftSection={<IconRefresh size={16} />}
            onClick={onRefresh}
            loading={taskRunning}
          >
            开始检测
          </Button>
        </Stack>
      </Center>
    );
  }

  const loader = report.loader ?? { present: false, root: '' };
  const patch = PATCH[report.patch_state] ?? PATCH.unknown;

  return (
    <Stack gap="md">
      {report.issues?.length > 0 && (
        <Alert color="red" icon={<IconAlertTriangle />} title="检测到问题">
          <Stack gap={4}>
            {report.issues.map((issue) => (
              <Text key={issue} size="sm">
                {issue}
              </Text>
            ))}
          </Stack>
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        <CardBlock title="补丁状态">
          <Badge color={patch.color} size="lg" variant="light">
            {patch.label}
          </Badge>
          <Text size="xs" c="dimmed" mt={8}>
            程序集内注入标记：{report.injected ? '有' : '无'}
          </Text>
        </CardBlock>

        <CardBlock title="游戏">
          <Stack gap={6}>
            <Field label="包名" value={report.bundle_id} />
            <Field label="版本" value={report.app_version || '?'} />
            <Field label="catalog" value={report.catalog || '?'} />
          </Stack>
        </CardBlock>

        <CardBlock title="代码包">
          <Stack gap={6}>
            <Field label="哈希" value={report.code_bundle_hash || '?'} />
            <Field
              label="大小"
              value={report.bundle_bytes ? `${report.bundle_bytes} B` : '?'}
            />
            <Field label="资产数" value={report.asset_count ?? '?'} />
          </Stack>
        </CardBlock>

        <CardBlock title="加载器">
          {loader.present ? (
            <Stack gap={6}>
              <Field label="根目录" value={loader.root} />
              <Field label="引导 DLL" value={loader.has_bootstrap ? '有' : '缺'} />
              <Field label="安卓 API" value={loader.has_api ? '有' : '无'} />
              <Field label="模组" value={`${loader.mod_count ?? 0} 个`} />
            </Stack>
          ) : (
            <Badge color="yellow" variant="light">
              未安装
            </Badge>
          )}
        </CardBlock>

        <CardBlock title="上次启动">
          {loader.mods_ok != null ? (
            <>
              <Group gap={8} align="baseline">
                <Text fz={22} fw={650}>
                  {loader.mods_ok}
                </Text>
                <Text size="sm" c="dimmed">
                  ok / {loader.mods_failed ?? 0} failed
                </Text>
              </Group>
              {loader.bootstrap_log && (
                <Text size="xs" c="dimmed" mt={6} ff="monospace" style={{ wordBreak: 'break-all' }}>
                  {loader.bootstrap_log}
                </Text>
              )}
            </>
          ) : (
            <Text size="sm" c="dimmed">
              还没有启动记录
            </Text>
          )}
        </CardBlock>

        <CardBlock title="引导日志尾部">
          {loader.bootstrap_tail?.length ? (
            <Code block maw="100%" style={{ maxHeight: 220, overflow: 'auto', fontSize: 11 }}>
              {loader.bootstrap_tail.join('\n')}
            </Code>
          ) : (
            <Text size="sm" c="dimmed">
              暂无
            </Text>
          )}
        </CardBlock>
      </SimpleGrid>

      {report.markers?.length > 0 && (
        <CardBlock title="注入标记">
          <Group gap={6}>
            {report.markers.map((marker) => (
              <Badge key={marker} size="sm" variant="default" ff="monospace">
                {marker}
              </Badge>
            ))}
          </Group>
        </CardBlock>
      )}
    </Stack>
  );
}
