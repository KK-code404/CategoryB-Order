import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.split('\\').join('/')
          if (normalized.includes('/node_modules/@vue/') || normalized.includes('/node_modules/vue/')) return 'vue'
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], clearMocks: true, restoreMocks: true },
})
