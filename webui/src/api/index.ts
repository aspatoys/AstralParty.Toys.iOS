import type { Bridge } from '../types';
import { createMockBridge } from './mock';

declare global {
  interface Window {
    pywebview?: { api?: Bridge };
  }
}

/**
 * 拿宿主桥。
 *
 * 在 pywebview 里它会稍晚一点注入；如果等到超时还没有（比如 `pnpm dev` 直接在浏览器里
 * 调界面），就退回假数据（`./mock`），这样前端可以脱离设备单独开发。
 */
export async function getBridge(timeoutMs = 1500): Promise<Bridge> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const api = window.pywebview?.api;
    if (api && typeof api.drain === 'function') return api;
    await new Promise((resolve) => setTimeout(resolve, 60));
  }
  return createMockBridge();
}

export const isMock = (bridge: Bridge): boolean => (bridge as { __mock?: boolean }).__mock === true;
