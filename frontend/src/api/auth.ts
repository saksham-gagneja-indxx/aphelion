/**
 * Auth API — owned by the antigravity session.
 * Handles the /api/me and /api/logout endpoints.
 */

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

export async function getMe(): Promise<User> {
  const res = await fetch('/api/me')
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Unauthorized')
    }
    throw await toError(res)
  }
  return res.json()
}

export async function logout(): Promise<{ ok: boolean }> {
  const res = await fetch('/api/logout', { method: 'POST' })
  if (!res.ok) throw await toError(res)
  return res.json()
}
