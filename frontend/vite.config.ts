import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api and /health to the backend, which keeps the
// browser same-origin. That matters for two reasons:
//   * uploads avoid a CORS preflight, so XHR upload progress works without
//     extra headers
//   * the browser never makes a cross-origin request, so CORS rules on the
//     backend are irrelevant during development
//
// The backend no longer runs locally: api.linkedin.com is unreachable from
// this machine (local endpoint-protection software intercepts TLS for that
// host), so it is deployed to Render and the proxy points there. Override with
// VITE_API_TARGET=http://127.0.0.1:5000 to develop against a local backend.
const DEFAULT_API_TARGET = 'https://social-media-manager-api-wk5g.onrender.com'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_TARGET || DEFAULT_API_TARGET

  // changeOrigin rewrites the Host header, which Render needs to route the
  // request to the right service.
  const proxy = {
    '/api': { target, changeOrigin: true },
    '/health': { target, changeOrigin: true },
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Fail loudly instead of silently moving to 5174. The OAuth redirect
      // URI is configured server-side for one exact origin, so a surprise
      // port change breaks sign-in in a way that is annoying to diagnose.
      strictPort: true,
      proxy,
    },
    preview: { port: 5173, strictPort: true, proxy },
  }
})
