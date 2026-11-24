import { useCallback, useEffect, useRef, useState } from 'react';
import { parentOf } from './format';

/** 历史栈上限：够用来回翻，又不至于把路径字符串都留在内存里。 */
const MAX_STACK = 200;

interface NavState {
  stack: string[];
  index: number;
}

/**
 * 目录历史：前进 / 后退 / 上级，和资源管理器一致。
 *
 * 鼠标侧键（X1/X2 在 DOM 里是 button 3 / 4）也接到前进后腿上；WebView2 默认会把它当
 * 自己的页面历史导航，所以这里在捕获阶段拦下并 preventDefault，避免整个界面被翻走。
 */
export function useNavHistory(root: string) {
  const [nav, setNav] = useState<NavState>({ stack: [root], index: 0 });
  const path = nav.stack[nav.index] ?? root;
  // 拖放轮询这类回调里要读「当前目录」，用 ref 拿最新值
  const pathRef = useRef(path);
  pathRef.current = path;

  const navigate = useCallback((next: string) => {
    setNav((prev) => {
      if (prev.stack[prev.index] === next) return prev;
      // 在历史中间点开新目录时，丢掉后面的分支（和浏览器一样）
      const stack = [...prev.stack.slice(0, prev.index + 1), next].slice(-MAX_STACK);
      return { stack, index: stack.length - 1 };
    });
  }, []);

  const back = useCallback(() => {
    setNav((prev) => (prev.index > 0 ? { ...prev, index: prev.index - 1 } : prev));
  }, []);

  const forward = useCallback(() => {
    setNav((prev) => (prev.index < prev.stack.length - 1 ? { ...prev, index: prev.index + 1 } : prev));
  }, []);

  const up = useCallback(() => {
    const parent = parentOf(path);
    if (parent !== path) navigate(parent);
  }, [navigate, path]);

  useEffect(() => {
    const onSideButton = (event: MouseEvent) => {
      if (event.button !== 3 && event.button !== 4) return;
      const target = event.target as HTMLElement | null;
      // 输入框里、弹窗里按侧键就交回系统
      if (target?.closest('input, textarea, [contenteditable="true"], [role="dialog"]')) return;
      event.preventDefault();
      event.stopPropagation();
      if (event.button === 3) back();
      else forward();
    };
    // Chromium 在 mouseup / auxclick 时才真正导航，三处都拦一下
    window.addEventListener('mousedown', onSideButton, true);
    window.addEventListener('mouseup', onSideButton, true);
    window.addEventListener('auxclick', onSideButton, true);
    return () => {
      window.removeEventListener('mousedown', onSideButton, true);
      window.removeEventListener('mouseup', onSideButton, true);
      window.removeEventListener('auxclick', onSideButton, true);
    };
  }, [back, forward]);

  return {
    path,
    pathRef,
    navigate,
    back,
    forward,
    up,
    canBack: nav.index > 0,
    canForward: nav.index < nav.stack.length - 1,
  };
}
