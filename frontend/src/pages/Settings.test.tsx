import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Settings from './Settings'
import { renderWithQuery } from '../test/utils'

// Backend responses for happy path
const STATUS_OK = {
  app: 'Social Media Manager',
  version: '1.0.0',
  environment: 'development',
  debug: true,
  database: 'sqlite',
  instagram_configured: false,
  claude_configured: false,
}

const USER_OK = {
  id: 1,
  instagram_username: 'local_dev_user',
  instagram_connected: false,
  linkedin_connected: false,
  timezone: 'Asia/Kolkata',
  account_name: 'LocalDev',
  is_active: true,
  created_at: '2026-08-14T10:00:00',
  last_login: null,
}

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

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('Settings page', () => {
  it('shows pending state while loading', () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {}))
    renderWithQuery(<Settings />)
    expect(screen.getByText('Loading connection status…')).toBeInTheDocument()
  })

  it('shows error banner when backend is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Bad Gateway', { status: 502, statusText: 'Bad Gateway' }),
    )
    renderWithQuery(<Settings />)

    await waitFor(() => {
      expect(screen.getByText('Could not reach backend')).toBeInTheDocument()
    })
  })

  /**
   * CRITICAL REGRESSION TEST: The "lying" bug.
   *
   * When the backend is down, Settings must NOT render the Instagram
   * connection card with "Not connected" / Username "—" — that looks
   * like a real answer when it's actually an outage.
   *
   * The fix: the connection card is gated on bothSuccess (both status
   * and user queries must succeed before any data is rendered).
   */
  it('error state must NOT render the connection card (lying bug regression)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Bad Gateway', { status: 502, statusText: 'Bad Gateway' }),
    )
    renderWithQuery(<Settings />)

    await waitFor(() => {
      expect(screen.getByText('Could not reach backend')).toBeInTheDocument()
    })

    // The connection card must NOT be visible
    expect(screen.queryByText('Instagram Connection')).not.toBeInTheDocument()
    expect(screen.queryByText('Not connected')).not.toBeInTheDocument()
    expect(screen.queryByText('Username')).not.toBeInTheDocument()
    expect(screen.queryByText('Credentials in .env')).not.toBeInTheDocument()
    expect(screen.queryByText('Reconnect Instagram')).not.toBeInTheDocument()
  })

  it('shows connection card when both queries succeed', async () => {
    mockFetchResponses({
      '/api/status': { status: 200, body: STATUS_OK },
      '/api/users/': { status: 200, body: USER_OK },
    })
    renderWithQuery(<Settings />)

    await waitFor(() => {
      expect(screen.getByText('Instagram Connection')).toBeInTheDocument()
    })
    expect(screen.getByText('@local_dev_user')).toBeInTheDocument()
    expect(screen.getByText('Not connected')).toBeInTheDocument()
    expect(screen.getByText('Asia/Kolkata')).toBeInTheDocument()
  })

  it('shows user-not-found error when status succeeds but user fails', async () => {
    mockFetchResponses({
      '/api/status': { status: 200, body: STATUS_OK },
      '/api/users/': { status: 404, body: { error: 'User not found' } },
    })
    renderWithQuery(<Settings />)

    await waitFor(() => {
      expect(screen.getByText('User not found')).toBeInTheDocument()
    })
    // Connection card must still be hidden
    expect(screen.queryByText('Instagram Connection')).not.toBeInTheDocument()
  })
})
