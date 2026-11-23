import { createTheme, type MantineColorsTuple } from '@mantine/core';

// iOS 系统色：蓝色为交互主色，绿色用于开关（iOS 的开关就是绿的）
const iosBlue: MantineColorsTuple = [
  '#e9f3ff', '#d2e6ff', '#a3caff', '#70abff', '#4a94ff', '#2f86ff', '#0a84ff',
  '#0a6fd6', '#005bbd', '#004a9e',
];

const iosGreen: MantineColorsTuple = [
  '#e9faef', '#d3f4e0', '#a5e9c3', '#74dda4', '#4fd38b', '#36cc79', '#30d158',
  '#17b046', '#0d9c3b', '#00852e',
];

const iosRed: MantineColorsTuple = [
  '#ffeceb', '#ffd6d4', '#ffa8a4', '#ff736c', '#ff4c43', '#ff332a', '#ff453a',
  '#d92a20', '#bd1c14', '#a30f09',
];

const iosGray: MantineColorsTuple = [
  '#f5f5f7', '#ebebef', '#d8d8de', '#c2c2ca', '#a7a7b0', '#94949e', '#8e8e93',
  '#75757c', '#5e5e64', '#48484d',
];

export const theme = createTheme({
  primaryColor: 'iosblue',
  colors: { iosblue: iosBlue, iosgreen: iosGreen, iosred: iosRed, iosgray: iosGray },
  defaultRadius: 'md',
  radius: { sm: '8px', md: '10px', lg: '14px', xl: '18px' },
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif',
  fontFamilyMonospace: 'ui-monospace, "SF Mono", "Cascadia Mono", Consolas, monospace',
  headings: { fontWeight: '600', sizes: { h4: { fontSize: '17px', fontWeight: '600' } } },
  components: {
    Button: {
      defaultProps: { radius: 'md' },
      styles: { root: { fontWeight: 500 } },
    },
    ActionIcon: { defaultProps: { radius: 'md' } },
    Card: {
      defaultProps: { radius: 'lg', withBorder: false, shadow: undefined },
      styles: { root: { background: 'var(--ios-elevated)', boxShadow: 'var(--ios-shadow)' } },
    },
    Paper: { defaultProps: { radius: 'lg' } },
    Switch: {
      defaultProps: { color: 'iosgreen', size: 'md' },
      styles: {
        track: { borderColor: 'transparent' },
        thumb: { borderColor: 'transparent' },
        label: { fontSize: '13px' },
      },
    },
    Checkbox: { defaultProps: { color: 'iosblue', radius: 'sm' } },
    Badge: {
      defaultProps: { radius: 'sm' },
      styles: { root: { textTransform: 'none', fontWeight: 500 } },
    },
    Modal: {
      defaultProps: {
        centered: true,
        radius: 'lg',
        overlayProps: { backgroundOpacity: 0.4, blur: 6 },
        transitionProps: { transition: 'pop', duration: 180 },
      },
    },
    Drawer: {
      defaultProps: {
        radius: 0,
        overlayProps: { backgroundOpacity: 0.4, blur: 6 },
      },
      styles: { content: { borderTopLeftRadius: 18, borderBottomLeftRadius: 18 } },
    },
    Table: {
      defaultProps: { highlightOnHover: true, verticalSpacing: 'sm', horizontalSpacing: 'md' },
    },
    NavLink: {
      defaultProps: { variant: 'light' },
      styles: {
        root: { borderRadius: 10, fontWeight: 500 },
        label: { fontSize: '13.5px' },
      },
    },
    Tooltip: { defaultProps: { radius: 'sm', withArrow: true, openDelay: 320 } },
    Notification: { defaultProps: { radius: 'md' } },
    TextInput: { defaultProps: { radius: 'md' } },
    Textarea: { defaultProps: { radius: 'md' } },
    Pagination: { defaultProps: { radius: 'md' } },
    Divider: { defaultProps: { color: 'var(--ios-separator)' } },
  },
});
