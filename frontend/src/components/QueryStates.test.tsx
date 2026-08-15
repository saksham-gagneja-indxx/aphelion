import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { QueryError, QueryPending, QueryEmpty } from './QueryStates'

describe('QueryError', () => {
  it('renders title', () => {
    render(<QueryError title="Something broke" />)
    expect(screen.getByText('Something broke')).toBeInTheDocument()
  })

  it('renders title and message', () => {
    render(<QueryError title="Failed" message="502 Bad Gateway" />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('502 Bad Gateway')).toBeInTheDocument()
  })

  it('omits message paragraph when not provided', () => {
    const { container } = render(<QueryError title="Oops" />)
    // Should have exactly one <p> (the title), not two
    expect(container.querySelectorAll('p')).toHaveLength(1)
  })
})

describe('QueryPending', () => {
  it('renders default label', () => {
    render(<QueryPending />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders custom label', () => {
    render(<QueryPending label="Fetching posts…" />)
    expect(screen.getByText('Fetching posts…')).toBeInTheDocument()
  })
})

describe('QueryEmpty', () => {
  it('renders title', () => {
    render(<QueryEmpty title="No data" />)
    expect(screen.getByText('No data')).toBeInTheDocument()
  })

  it('renders title and message', () => {
    render(<QueryEmpty title="Empty" message="Try uploading something." />)
    expect(screen.getByText('Empty')).toBeInTheDocument()
    expect(screen.getByText('Try uploading something.')).toBeInTheDocument()
  })
})
