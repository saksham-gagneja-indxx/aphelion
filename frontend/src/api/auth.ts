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

    // When the consent flow ran in a tab we opened, hand back to the opener
    // rather than leaving a second copy of the app running. localStorage is
    // shared across same-origin tabs, so the token written above is already
    // visible there; the opener picks it up from the 'storage' event.
    if (window.opener && window.opener !== window) {
      window.close()
    }
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
  /** Sandboxed try-it-out account: cannot publish, never an administrator. */
  is_guest: boolean
  linkedin_connected: boolean
  avatar_url: string | null
  /**
   * Whether ANY LinkedIn app is available to connect through - the server's
   * shared one, or this account's own. Distinct from linkedin_connected:
   * this can be true before anyone has actually clicked through the OAuth
   * grant. Used to decide whether a fresh sign-in needs to land on Setup at
   * all, or whether there's nothing left to register.
   */
  linkedin_app_configured: boolean
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

/** True when this deployment has a Clerk publishable key configured. Gates
 *  whether Clerk's components/hooks are mounted at all - see main.tsx. */
export const CLERK_ENABLED = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY)

/**
 * Exchange a verified Clerk session token for this app's own session token.
 *
 * The backend re-verifies the token against Clerk's JWKS before trusting
 * anything in it - this call carries no other credential and needs none.
 * On success the app token is stored under the same key everything else in
 * this module reads, so nothing downstream needs to know Clerk exists.
 */
export async function bridgeClerkSession(clerkToken: string): Promise<User> {
  const res = await fetch(`${API_BASE}/api/auth/clerk/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: clerkToken }),
  })
  if (!res.ok) throw await toError(res)
  const body = (await res.json()) as { token: string; user: User }
  localStorage.setItem(SESSION_KEY, body.token)
  return body.user
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
  /**
   * Whether the grant actually carries w_member_social. Signing in
   * successfully says nothing about this: without the "Share on LinkedIn"
   * product the account connects fine and every publish then fails.
   */
  can_publish: boolean
  granted_scopes: string[] | null
  token_expires_at: string | null
  token_expired: boolean
}

export interface SetupStep {
  id: 'app' | 'redirect' | 'connect' | 'publish'
  title: string
  done: boolean
  detail: string | null
}

export interface SetupState {
  steps: SetupStep[]
  complete: boolean
  redirect_uri: string
  is_admin: boolean
  has_own_linkedin_app: boolean
  own_linkedin_client_id: string | null
}

/** Save this account's own LinkedIn app credentials (see backend/api/integrations_routes.py). */
export async function saveLinkedInCredentials(clientId: string, clientSecret: string): Promise<void> {
  const res = await apiFetch('/api/integrations/linkedin/credentials', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
  })
  if (!res.ok) throw await toError(res)
}

/** Drop this account's own app and fall back to the server's shared one. */
export async function clearLinkedInCredentials(): Promise<void> {
  const res = await apiFetch('/api/integrations/linkedin/credentials', { method: 'DELETE' })
  if (!res.ok) throw await toError(res)
}

/** Whether this server offers guest accounts. */
export async function getGuestEnabled(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/guest/status`)
    if (!res.ok) return false
    return Boolean((await res.json()).enabled)
  } catch {
    // A server that cannot be reached simply does not offer the option.
    return false
  }
}

/**
 * Create a sandboxed guest account and sign in as it.
 *
 * Not a bypass: this returns an ordinary session for an ordinary account that
 * happens to be barred from publishing and from ever being an administrator.
 */
export async function signInAsGuest(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/guest`, { method: 'POST' })
  if (!res.ok) throw await toError(res)
  const body = (await res.json()) as { token: string }
  localStorage.setItem(SESSION_KEY, body.token)
}

/** What the caller still has to do before they can publish. */
export async function getSetupState(): Promise<SetupState> {
  const res = await apiFetch('/api/setup/state')
  if (!res.ok) throw await toError(res)
  return res.json()
}

/** Storage key holding the session token. Shared across same-origin tabs. */
export const SESSION_KEY = 'smm.session'

/**
 * Open the LinkedIn consent screen in a new tab.
 *
 * `openBlankTab` must be called synchronously from the click handler: popup
 * blockers only allow window.open inside a user gesture, and the authorize URL
 * for a re-connect has to be fetched first (it needs the bearer token, which a
 * top-level navigation cannot send). So the tab is claimed on click and its
 * location set once the URL arrives.
 */
export function openBlankTab(): Window | null {
  return window.open('', '_blank')
}

/** The sign-in entry point is public, so it can be opened directly. */
export function linkedInLoginUrl(): string {
  return `${API_BASE}/api/auth/linkedin/login`
}

/**
 * Authorize URL for re-connecting the signed-in user's LinkedIn account.
 *
 * Fetched rather than navigated to: /start requires a bearer token, so
 * pointing the browser at it directly just returns 401.
 */
export async function getLinkedInAuthorizeUrl(): Promise<string> {
  const res = await apiFetch('/api/auth/linkedin/start?format=json')
  if (!res.ok) throw await toError(res)
  const body = (await res.json()) as { url: string }
  return body.url
}

/**
 * Notify when another tab signs in, so the page that opened the consent tab
 * can refresh itself. The 'storage' event fires only in OTHER tabs, which is
 * exactly the direction needed here.
 */
export function onSessionChangedInAnotherTab(handler: () => void): () => void {
  const listener = (e: StorageEvent) => {
    if (e.key === SESSION_KEY && e.newValue) handler()
  }
  window.addEventListener('storage', listener)
  return () => window.removeEventListener('storage', listener)
}

export async function getLinkedInStatus(userId: number): Promise<LinkedInStatus> {
  const res = await apiFetch(`/api/auth/linkedin/status?user_id=${userId}`)
  if (!res.ok) throw await toError(res)
  return res.json()
}
