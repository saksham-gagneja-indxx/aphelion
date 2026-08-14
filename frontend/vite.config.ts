import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api and /health to the Flask backend on :5000.
// This keeps the browser same-origin, so uploads don't hit CORS preflight
// and XHR upload progress works without extra headers.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    },
  },
})
