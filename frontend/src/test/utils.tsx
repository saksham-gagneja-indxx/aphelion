/**
 * Test utilities — shared wrapper that provides QueryClientProvider
 * for components that use TanStack Query hooks.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import { type ReactElement } from 'react'
import { CurrentUserProvider } from '../current-user'
import type { User } from '../api/auth'

/**
 * Stand-in for the signed-in user. Pages read their id from context rather than
 * a hardcoded constant, so rendering one outside a provider is a wiring error
 * the hook throws on - tests have to supply a user like the app does.
 */
export const TEST_USER: User = {
  id: 1,
  name: 'Test User',
  email: 'test@example.com',
  role: 'operator',
  linkedin_connected: false,
  avatar_url: null,
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        retryDelay: 0,
        gcTime: 0,
        // Important: disable networkMode pausing in tests
        networkMode: 'always',
      },
      mutations: {
        networkMode: 'always',
      },
    },
  })
}

export function renderWithQuery(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'> & { user?: User },
) {
  const { user = TEST_USER, ...renderOptions } = options ?? {}
  const client = createTestQueryClient()
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <CurrentUserProvider user={user}>{children}</CurrentUserProvider>
      </QueryClientProvider>
    )
  }
  return { ...render(ui, { wrapper: Wrapper, ...renderOptions }), client }
}
