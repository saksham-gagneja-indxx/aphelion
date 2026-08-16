import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { SpeedInsights } from '@vercel/speed-insights/react'
import { Analytics } from '@vercel/analytics/react'
import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Uploads are user-driven; aggressive refetching just adds noise.
      refetchOnWindowFocus: false,
      retry: 1,
      // The default ("online") PAUSES queries whenever the browser reports
      // itself offline: they sit at status "pending" / fetchStatus "paused"
      // forever, never erroring, so a dead backend renders as a permanent
      // loading spinner instead of an error. This app only ever talks to
      // localhost, where that heuristic is wrong - always attempt the request
      // and let real failures surface.
      networkMode: 'always',
    },
    mutations: {
      networkMode: 'always',
    },
  },
})

// This app only ever talks to localhost, so it is never meaningfully
// "offline". Without this, the online manager can settle into an offline
// belief and park every query at fetchStatus "paused" - pending forever,
// never erroring - so a stopped backend renders as an endless spinner.
onlineManager.setOnline(true)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
          <SpeedInsights />
          <Analytics />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
