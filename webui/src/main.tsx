import React from 'react';
import ReactDOM from 'react-dom/client';
import { MantineProvider } from '@mantine/core';
import { ModalsProvider } from '@mantine/modals';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import './index.css';

import App from './App';
import { theme } from './theme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, staleTime: 2000 },
  },
});

// 页面里的未捕获异常交给宿主，进「输出」面板；不然界面挂了只能看到白屏
function report(text: string) {
  const api = (window as unknown as {
    pywebview?: { api?: { client_error?: (message: string) => void } };
  }).pywebview?.api;
  api?.client_error?.(text);
}

window.addEventListener('error', (event) => {
  report(`${event.message} @ ${event.filename}:${event.lineno}`);
});
window.addEventListener('unhandledrejection', (event) => {
  report(`未处理的 Promise 拒绝：${String(event.reason)}`);
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <ModalsProvider>
        <Notifications position="top-right" autoClose={3500} />
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </ModalsProvider>
    </MantineProvider>
  </React.StrictMode>,
);
