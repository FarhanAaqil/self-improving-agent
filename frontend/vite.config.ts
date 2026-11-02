import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API = 'http://127.0.0.1:8000'
const proxied = ['/health', '/models', '/sandbox', '/generate', '/execute', '/runs', '/eval', '/memory', '/compare', '/shared', '/usage', '/stats', '/metrics']

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Only API calls go to FastAPI; page routes like /runs/:id are served by Vite
    proxy: Object.fromEntries(
      proxied.map((path) => [
        path,
        {
          target: API,
          bypass: (req: { headers: { accept?: string } }) =>
            req.headers.accept?.includes('text/html') ? '/index.html' : undefined,
        },
      ]),
    ),
  },
})
