/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Pinned regardless of any local .env/.env.local: `import.meta.env.VITE_*`
  // is inlined at transform time, not read dynamically, so a developer's own
  // Clerk key (needed to run the dev server against the real service) would
  // otherwise leak into every test run and silently flip CLERK_ENABLED to
  // true - exactly the failure mode tests/conftest.py's ISOLATED_ENV_VARS
  // exists to prevent on the backend, just hit here on the frontend instead.
  define: {
    'import.meta.env.VITE_CLERK_PUBLISHABLE_KEY': JSON.stringify(''),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
