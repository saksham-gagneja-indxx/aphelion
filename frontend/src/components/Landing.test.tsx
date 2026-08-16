import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest'
import Landing from './Landing'
import { renderWithQuery } from '../test/utils'

/** Landing asks the server whether to offer guest access before showing it. */
function mockGuestEnabled(enabled: boolean) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = typeof input === 'string' ? input : (input as Request).url
    if (url.includes('/api/auth/guest/status')) {
      return new Response(JSON.stringify({ enabled }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response('Not found', { status: 404 })
  })
}

describe('Landing page', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
    mockGuestEnabled(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the hero and a way in', () => {
    renderWithQuery(<Landing />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Schedule once.Ship every reel on time.',
    )
    // Nav and hero both offer it, and both start the same OAuth flow.
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Sign in with LinkedIn/ }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })

  it('links the docs in-app rather than out to the repository', () => {
    renderWithQuery(<Landing />)
    for (const link of screen.getAllByRole('link', { name: /docs/i })) {
      expect(link).toHaveAttribute('href', '/docs')
    }
  })

  it('offers guest access only when the server allows it', async () => {
    mockGuestEnabled(true)
    renderWithQuery(<Landing />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /guest/i })).toBeInTheDocument()
    })
    // The limit is stated up front, not discovered at publish time.
    expect(screen.getByText(/Publishing needs\s+LinkedIn/)).toBeInTheDocument()
  })

  it('hides guest access when the server has it switched off', async () => {
    mockGuestEnabled(false)
    renderWithQuery(<Landing />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: /guest/i })).not.toBeInTheDocument()
  })

  it('displays specific error for ?linkedin=denied', () => {
    window.history.pushState({}, '', '/?linkedin=denied')
    renderWithQuery(<Landing />)
    expect(
      screen.getByText(
        'You declined the LinkedIn authorization request. Please authorize to sign in.',
      ),
    ).toBeInTheDocument()
  })

  it('displays generic error for unknown status', () => {
    window.history.pushState({}, '', '/?linkedin=unknown_error')
    renderWithQuery(<Landing />)
    expect(screen.getByText('Authentication failed: unknown_error')).toBeInTheDocument()
  })

  it('ignores ?linkedin=connected', () => {
    window.history.pushState({}, '', '/?linkedin=connected')
    renderWithQuery(<Landing />)
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })
})
