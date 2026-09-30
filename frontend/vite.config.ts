/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Django отдаёт собранное как статику: /static/events/vue/...
const STATIC_BASE = '/static/events/vue/'

export default defineConfig({
  plugins: [vue()],
  base: STATIC_BASE,
  build: {
    outDir: fileURLToPath(new URL('../events/static/events/vue', import.meta.url)),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      // по одной точке входа на экран, которые Django встраивает в свои шаблоны
      input: {
        entry: 'src/entries/entry.ts',
        results: 'src/entries/results.ts',
        matrix: 'src/entries/matrix.ts',
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // страница на :8000 грузит скрипты и шрифты отсюда, поэтому адреса в модулях должны быть абсолютными
    origin: 'http://localhost:5173',
    cors: true,
    // на bind-mount из Windows в Docker события файловой системы не доходят
    watch: process.env.VITE_POLLING ? { usePolling: true, interval: 300 } : undefined,
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
})
