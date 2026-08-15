import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import Admin from './Admin'
import { renderWithQuery } from '../test/utils'

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

const USERS_RESPONSE = {
  users: [
    {
      id: 1,
      name: 'Admin User',
      email: 'admin@example.com',
      role: 'admin',
      is_active: true,
      linkedin_connected: true,
      last_seen_at: '2026-08-14T10:00:00Z',
      post_count: 5,
    },
    {
      id: 2,
      name: 'Operator User',
      email: 'op@example.com',
      role: 'operator',
      is_active: false,
      linkedin_connected: false,
      last_seen_at: null,
      post_count: 0,
    },
  ]
}

const AUDIT_RESPONSE = {
  events: [
    {
      id: 1,
      actor_name: 'Admin User',
      action: 'changed role of',
      target: 'Operator User to admin',
      created_at: '2026-08-14T11:00:00Z',
    }
  ]
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('Admin page', () => {
  it('renders "Not Authorized" for operators', async () => {
    mockFetchResponses({
      '/api/me': { status: 200, body: { id: 2, role: 'operator' } },
    })

    renderWithQuery(<Admin />)

    await waitFor(() => {
      expect(screen.getByText('Not Authorized')).toBeInTheDocument()
    })
    
    // The admin panel should not render
    expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument()
  })

  it('renders admin table and audit log for admins', async () => {
    mockFetchResponses({
      '/api/me': { status: 200, body: { id: 1, role: 'admin' } },
      '/api/admin/users': { status: 200, body: USERS_RESPONSE },
      '/api/admin/audit': { status: 200, body: AUDIT_RESPONSE },
    })

    renderWithQuery(<Admin />)

    await waitFor(() => {
      expect(screen.getByText('Admin Panel')).toBeInTheDocument()
    })

    // Check users table
    expect(screen.getByText('Admin User')).toBeInTheDocument()
    expect(screen.getByText('admin@example.com')).toBeInTheDocument()
    expect(screen.getByText('Operator User')).toBeInTheDocument()
    
    // Check audit log
    expect(screen.getByText('changed role of')).toBeInTheDocument()
    expect(screen.getByText('Operator User to admin')).toBeInTheDocument()
  })

  it('shows error banner when admin data fails to load', async () => {
    mockFetchResponses({
      '/api/me': { status: 200, body: { id: 1, role: 'admin' } },
      '/api/admin/users': { status: 403, body: { error: 'Forbidden' } },
      '/api/admin/audit': { status: 200, body: AUDIT_RESPONSE },
    })

    renderWithQuery(<Admin />)

    await waitFor(() => {
      expect(screen.getByText('Failed to load users')).toBeInTheDocument()
    })
  })
})
