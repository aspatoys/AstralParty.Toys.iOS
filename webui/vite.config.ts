import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base 用相对路径：pywebview 的 http_server 从 dist 目录起服务，相对路径最稳。
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2020',
    chunkSizeWarningLimit: 1200,
  },
  server: { port: 5273, strictPort: false },
});
