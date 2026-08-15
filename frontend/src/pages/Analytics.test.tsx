import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Analytics from './Analytics'
import { renderWithQuery } from '../test/utils'

// Mock the fetch layer. We mock the global fetch since getAnalytics
// in api/client.ts calls fetch() directly.

const ANALYTICS_DATA = {
  total_posts_analyzed: 42,
  average_likes: 318.5,
  average_comments: 24.3,
  best_posting_hours: [18, 21, 12],
  best_posting_days: [2, 4, 6],
  peak_engagement_hour: 21,
  confidence: 90,
  last_updated: '2026-08-14T12:00:00',
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('Analytics page', () => {
  it('shows a spinner while pending', () => {
    // Never-resolving fetch to keep the query in pending state
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {}))
    renderWithQuery(<Analytics />)
    expect(screen.getByText('Loading analytics…')).toBeInTheDocument()
  })

  it('shows error banner when fetch fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: 'Internal Server Error' }), {
        status: 500,
        statusText: 'Internal Server Error',
      }),
    )
    renderWithQuery(<Analytics />)

    await waitFor(() => {
      expect(screen.getByText('Failed to load analytics')).toBeInTheDocument()
    })
  })

  it('shows empty state when backend returns no data (isSuccess + null)', async () => {
    // Backend returns 200 with { message: "No analytics data available" }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ message: 'No analytics data available' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithQuery(<Analytics />)

    await waitFor(() => {
      expect(screen.getByText('No analytics data available')).toBeInTheDocument()
    })
    // Must NOT show error banner
    expect(screen.queryByText('Failed to load analytics')).not.toBeInTheDocument()
    expect(
      screen.getByText('No posts published yet — analytics will appear here once you publish.'),
    ).toBeInTheDocument()
  })

  it('shows metric cards when data exists', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(ANALYTICS_DATA), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderWithQuery(<Analytics />)

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument()
    })
    expect(screen.getByText('318.5')).toBeInTheDocument()
    expect(screen.getByText('24.3')).toBeInTheDocument()
    expect(screen.getByText('90%')).toBeInTheDocument()
  })

  it('does NOT show empty state when fetch errors (prevents the "lying" bug)', async () => {
    // This is the regression test: a failed fetch must never render
    // "No analytics data available" — that would look like a real answer.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Bad Gateway', { status: 502, statusText: 'Bad Gateway' }),
    )
    renderWithQuery(<Analytics />)

    await waitFor(() => {
      expect(screen.getByText('Failed to load analytics')).toBeInTheDocument()
    })
    expect(screen.queryByText('No analytics data available')).not.toBeInTheDocument()
  })
})
