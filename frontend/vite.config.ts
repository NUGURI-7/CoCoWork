import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          // ldrs 的所有 web component 都以 l- 开头（l-miyagi / l-ring / l-dot-pulse 等）
          isCustomElement: (tag) => tag.startsWith('l-'),
        },
      },
    }),
    vueDevTools(),
    tailwindcss(),
  ],
  server: {
    cors: true,
    host: '0.0.0.0', // 允许内网访问
    port: 7777,
    strictPort: true,
    // 将 /api 请求转发到后端，开发时统一走相对路径 /api
    // 生产由 nginx 处理，前端代码不感知后端端口
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7999',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
