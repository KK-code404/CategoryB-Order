import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 配置 React 构建及本地 API 代理，使开发与容器部署使用同一接口路径。
export default defineConfig({
  plugins: [react()],
  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将稳定 React 运行时与业务入口拆分缓存，降低后续更新时的重复下载。
  build: {
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.split('\\').join('/')
          if (normalized.includes('/node_modules/react/') || normalized.includes('/node_modules/react-dom/') || normalized.includes('/node_modules/scheduler/')) return 'react'
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
