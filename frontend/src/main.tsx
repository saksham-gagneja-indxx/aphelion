import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { ClerkProvider } from '@clerk/clerk-react'
import { SpeedInsights } from '@vercel/speed-insights/react'
import { Analytics } from '@vercel/analytics/react'
import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import { clerkAppearance } from './clerkAppearance'
import './index.css'

// Unset in any environment that hasn't configured Clerk yet: rather than
// crash the whole app on a missing key, ClerkProviderOrPassthrough (below)
// skips the provider entirely and the LinkedIn-login path keeps working
// exactly as it did before Clerk existed.
const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as
  | string
  | undefined

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

/** Wraps with ClerkProvider only when a publishable key is configured, so a
 *  deployment that hasn't set one up yet still boots and serves the
 *  LinkedIn-only sign-in path rather than throwing on a missing key. */
function ClerkProviderOrPassthrough({ children }: { children: ReactNode }) {
  if (!CLERK_PUBLISHABLE_KEY) return <>{children}</>
  return (
    <ClerkProvider
      publishableKey={CLERK_PUBLISHABLE_KEY}
      afterSignOutUrl="/"
      appearance={clerkAppearance}
    >
      {children}
    </ClerkProvider>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <ClerkProviderOrPassthrough>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
            <SpeedInsights />
            <Analytics />
          </BrowserRouter>
        </QueryClientProvider>
      </ClerkProviderOrPassthrough>
    </ErrorBoundary>
  </StrictMode>,
)
