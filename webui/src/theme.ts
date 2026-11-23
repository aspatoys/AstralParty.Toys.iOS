import { createTheme, type MantineColorsTuple } from '@mantine/core';

// 取自启动图标的莓红，和安卓端/Toys 的配色同一家族
const berry: MantineColorsTuple = [
  '#ffe9ef',
  '#ffd1dd',
  '#f89db6',
  '#f3668e',
  '#ef3c6c',
  '#ed2157',
  '#ed0f4c',
  '#d3003e',
  '#bd0036',
  '#a5002b',
];

export const theme = createTheme({
  primaryColor: 'berry',
  colors: { berry },
  defaultRadius: 'md',
  fontFamily:
    'system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif',
  fontFamilyMonospace:
    'ui-monospace, "Cascadia Mono", Consolas, "SF Mono", Menlo, monospace',
  headings: { fontWeight: '650' },
});
