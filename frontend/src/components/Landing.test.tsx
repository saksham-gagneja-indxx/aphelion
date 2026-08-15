import { render, screen } from '@testing-library/react'
import { describe, expect, it, beforeEach } from 'vitest'
import Landing from './Landing'

describe('Landing page', () => {
  beforeEach(() => {
    // Reset URL before each test
    window.history.pushState({}, '', '/')
  })

  it('renders the hero and a way in', () => {
    render(<Landing />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Schedule once.Ship every reel on time.',
    )
    // Nav and hero both offer it, and both start the same OAuth flow.
    expect(screen.getAllByRole('button', { name: 'Start for free' })).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })

  it('displays specific error for ?linkedin=denied', () => {
    window.history.pushState({}, '', '/?linkedin=denied')
    render(<Landing />)
    expect(screen.getByText('You declined the LinkedIn authorization request. Please authorize to sign in.')).toBeInTheDocument()
  })

  it('displays generic error for unknown status', () => {
    window.history.pushState({}, '', '/?linkedin=unknown_error')
    render(<Landing />)
    expect(screen.getByText('Authentication failed: unknown_error')).toBeInTheDocument()
  })

  it('ignores ?linkedin=connected', () => {
    window.history.pushState({}, '', '/?linkedin=connected')
    render(<Landing />)
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })
})
