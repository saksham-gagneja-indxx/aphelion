import { render, screen } from '@testing-library/react'
import { describe, expect, it, beforeEach } from 'vitest'
import Login from './Login'

describe('Login component', () => {
  beforeEach(() => {
    // Reset URL before each test
    window.history.pushState({}, '', '/')
  })

  it('renders correctly without errors', () => {
    render(<Login />)
    expect(screen.getByText('Sign in to Reel Automation')).toBeInTheDocument()
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })

  it('displays specific error for ?linkedin=denied', () => {
    window.history.pushState({}, '', '/?linkedin=denied')
    render(<Login />)
    expect(screen.getByText('You declined the LinkedIn authorization request. Please authorize to sign in.')).toBeInTheDocument()
  })

  it('displays generic error for unknown status', () => {
    window.history.pushState({}, '', '/?linkedin=unknown_error')
    render(<Login />)
    expect(screen.getByText('Authentication failed: unknown_error')).toBeInTheDocument()
  })

  it('ignores ?linkedin=connected', () => {
    window.history.pushState({}, '', '/?linkedin=connected')
    render(<Login />)
    expect(screen.queryByText(/Authentication failed/)).not.toBeInTheDocument()
  })
})
