import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { renderWithQuery } from './test/utils'

function mockFetchResponses(responses: Record<string, { status: number; body: unknown }>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = typeof input === 'string' ? input : (input as Request).url
    for (const [pattern, resp] of Object.entries(responses)) {
      if (url.includes(pattern)) {
        return new Response(JSON.stringify(resp.body), {
          status: resp.status,
          headers: { 'Content-Type': 'application/json' },
        })
      }
    }
    return new Response('Not found', { status: 404 })
  })
}

const OPERATOR_USER = {
  id: 1,
  name: 'John Doe',
  email: 'john@example.com',
  role: 'operator',
  linkedin_connected: true,
  avatar_url: null,
}

const ADMIN_USER = {
  ...OPERATOR_USER,
  role: 'admin',
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('App routing and auth gate', () => {
  it('shows login gate on 401', async () => {
    mockFetchResponses({
      '/api/me': { status: 401, body: { error: 'Unauthorized' } },
    })

    // MemoryRouter is needed because App defines <Routes> but the outer 
    // BrowserRouter is usually in main.tsx. 
    renderWithQuery(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    })

    // The signed-out landing page, not the app
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Schedule once.')

    // The main app layout should NOT be visible.
    //
    // Asserting on 'Reel Automation' does not work: the landing page carries
    // the same wordmark, so that text is legitimately present. Nor can we
    // assert there is no <nav> — the landing page has its own marketing one.
    // Assert on the app's own nav links, which exist only once signed in.
    expect(screen.queryByRole('link', { name: 'Upload' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Queue' })).not.toBeInTheDocument()
  })

  it('renders app and hides Admin nav for operator', async () => {
    mockFetchResponses({
      '/api/me': { status: 200, body: OPERATOR_USER },
    })

    renderWithQuery(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )

    await waitFor(() => {
      // The header title should be visible
      const elements = screen.getAllByText('Reel Automation')
      expect(elements.length).toBeGreaterThan(0)
    })
    
    // User name should be visible in header
    expect(screen.getByText('John Doe')).toBeInTheDocument()
    
    // Admin nav should NOT be present
    expect(screen.queryByText('Admin')).not.toBeInTheDocument()
  })

  it('renders Admin nav for admin user', async () => {
    mockFetchResponses({
      '/api/me': { status: 200, body: ADMIN_USER },
    })

    renderWithQuery(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )

    await waitFor(() => {
      // Admin nav should be present
      expect(screen.getByText('Admin')).toBeInTheDocument()
    })
  })
})
