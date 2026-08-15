import { render, screen } from '@testing-library/react'
import { describe, expect, it, beforeEach } from 'vitest'
import Login from './Login'

describe('Login component', () => {
  const originalLocation = window.location

  beforeEach(() => {
    // Reset window.location before each test
    delete (window as any).location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, search: '' },
      writable: true,
    })
  })

  it('renders correctly without errors', () => {
    render(<Login />)
    expect(screen.getByText('Sign in to Reel Automation')).toBeInTheDocument()
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })

  it('displays specific error for ?linkedin=denied', () => {
    window.location.search = '?linkedin=denied'
    render(<Login />)
    expect(screen.getByText('You declined the LinkedIn authorization request. Please authorize to sign in.')).toBeInTheDocument()
  })

  it('displays generic error for unknown status', () => {
    window.location.search = '?linkedin=unknown_error'
    render(<Login />)
    expect(screen.getByText('Authentication failed: unknown_error')).toBeInTheDocument()
  })

  it('ignores ?linkedin=connected', () => {
    window.location.search = '?linkedin=connected'
    render(<Login />)
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })
})
