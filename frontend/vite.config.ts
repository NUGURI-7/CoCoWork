import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // TanStack Router 文件式路由：扫描 src/routes/**/*.tsx 自动生成 routeTree.gen.ts
    TanStackRouterVite({ target: 'react', autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  server: {
    cors: true,
    host: '0.0.0.0',
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
