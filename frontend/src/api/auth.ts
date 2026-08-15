/**
 * Auth API — owned by the antigravity session.
 * Handles the /api/me and /api/logout endpoints.
 */

// 1. On app boot, before the first /api/me call: extract token from fragment
if (typeof window !== 'undefined' && window.location.hash.includes('token=')) {
  const match = window.location.hash.match(/token=([^&]+)/)
  if (match && match[1]) {
    localStorage.setItem('smm.session', match[1])
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
  }
}

/**
 * Backend origin. Empty string means same-origin (dev proxy / same-host deploy).
 * Set VITE_API_URL when the frontend and backend are on different origins
 * (e.g. frontend on Vercel, backend on Render).
 */
export const API_BASE = import.meta.env.VITE_API_URL ?? ''

function resolveUrl(input: RequestInfo | URL): RequestInfo | URL {
  if (typeof input === 'string' && input.startsWith('/')) {
    return `${API_BASE}${input}`
  }
  return input
}

export interface User {
  id: number
  name: string
  email: string
  role: 'admin' | 'operator'
  linkedin_connected: boolean
  avatar_url: string | null
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

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = localStorage.getItem('smm.session')
  const headers = new Headers(init?.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(resolveUrl(input), { ...init, headers })

  if (res.status === 401) {
    localStorage.removeItem('smm.session')
  }

  return res
}

export async function getMe(): Promise<User> {
  const res = await apiFetch('/api/me')
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Unauthorized')
    }
    if (res.status === 403) {
      throw new Error('Forbidden')
    }
    throw await toError(res)
  }
  return res.json()
}

export async function logout(): Promise<{ ok: boolean }> {
  const res = await apiFetch('/api/logout', { method: 'POST' })
  localStorage.removeItem('smm.session') // Clear client copy immediately
  if (!res.ok) {
    // We still clear the token on 401, which apiFetch does, but if it fails otherwise we throw
    throw await toError(res)
  }
  return res.json()
}

export interface LinkedInStatus {
  app_configured: boolean
  connected: boolean
  person_urn: string | null
  email: string | null
  token_expires_at: string | null
  token_expired: boolean
}

export async function getLinkedInStatus(userId: number): Promise<LinkedInStatus> {
  const res = await apiFetch(`/api/auth/linkedin/status?user_id=${userId}`)
  if (!res.ok) throw await toError(res)
  return res.json()
}
