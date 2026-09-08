import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/generate': 'http://127.0.0.1:8000',
      '/execute': 'http://127.0.0.1:8000',
      '/generate-and-repair': 'http://127.0.0.1:8000',
      '/runs': 'http://127.0.0.1:8000',
      '/eval': 'http://127.0.0.1:8000',
    },
  },
})
