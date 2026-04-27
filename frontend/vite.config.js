import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/hsh-api': {
        target: 'https://apicheckpricev3.huasengheng.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/hsh-api/, '')
      }
    }
  }
})