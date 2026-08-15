/**
 * Admin API — owned by the antigravity session.
 * Handles endpoints for the Admin panel.
 */

import { apiFetch } from './auth'

export interface AdminUser {
  id: number
  name: string
  email: string
  role: 'admin' | 'operator'
  is_active: boolean
  linkedin_connected: boolean
  last_seen_at: string | null
  post_count: number
}

export interface AuditLogEvent {
  id: number
  actor_name: string
  action: string
  target: string
  created_at: string
}

async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json()
    if (body?.error) return new Error(body.error)
  } catch {
    // ignore
  }
  return new Error(`Request failed (${res.status})`)
}

export async function getUsers(): Promise<{ users: AdminUser[] }> {
  const res = await apiFetch('/api/admin/users')
  if (!res.ok) {
    if (res.status === 403) throw new Error('Forbidden')
    throw await toError(res)
  }
  return res.json()
}

export async function updateUserRole(id: number, role: 'admin' | 'operator'): Promise<void> {
  const res = await apiFetch(`/api/admin/users/${id}/role`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  })
  if (!res.ok) throw await toError(res)
}

export async function updateUserActive(id: number, is_active: boolean): Promise<void> {
  const res = await apiFetch(`/api/admin/users/${id}/active`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active }),
  })
  if (!res.ok) throw await toError(res)
}

export async function getAuditLogs(limit: number = 100): Promise<{ events: AuditLogEvent[] }> {
  const res = await apiFetch(`/api/admin/audit?limit=${limit}`)
  if (!res.ok) {
    if (res.status === 403) throw new Error('Forbidden')
    throw await toError(res)
  }
  return res.json()
}
