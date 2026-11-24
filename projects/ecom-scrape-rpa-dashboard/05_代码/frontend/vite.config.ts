import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev 5187（工作流端口分配表固定）；/api 反代到后端 5A 的 8094（§6.5）
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5187,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8094',
        changeOrigin: false,
      },
    },
  },
})
