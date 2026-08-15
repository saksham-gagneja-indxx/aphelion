/**
 * Test utilities — shared wrapper that provides QueryClientProvider
 * for components that use TanStack Query hooks.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import { type ReactElement } from 'react'

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
  options?: Omit<RenderOptions, 'wrapper'>,
) {
  const client = createTestQueryClient()
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
  return { ...render(ui, { wrapper: Wrapper, ...options }), client }
}
