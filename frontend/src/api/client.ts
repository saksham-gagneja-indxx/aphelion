import type { AnalyticsSummary, ApiError, ApiStatus, HealthStatus, UploadResponse, UserInfo } from './types'
import { apiFetch } from './auth'

/**
 * Storage key for the session token.
 *
 * MUST match the key used in api/auth.ts. Duplicated only because XHR cannot
 * go through apiFetch (which wraps fetch), and fetch has no upload-progress
 * events - so the upload path has to read the token itself.
 */
const SESSION_KEY = 'smm.session'

/**
 * Extract the backend's error message from a failed response.
 * Falls back to the status line when the body isn't the expected JSON shape
 * (e.g. Flask's HTML 413 page when a body exceeds MAX_CONTENT_LENGTH).
 */
async function toError(res: Response): Promise<Error> {
  try {
    const body = (await res.json()) as ApiError
    if (body?.error) return new Error(body.error)
  } catch {
    // non-JSON body
  }
  return new Error(`Request failed (${res.status} ${res.statusText})`)
}

/**
 * All API calls go through apiFetch so the session token is attached. Every
 * /api/* route requires a bearer token; a plain fetch() here returns 401 and
 * the caller sees an unexplained failure.
 */
async function getJson<T>(path: string): Promise<T> {
  const res = await apiFetch(path)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as T
}

export const getStatus = () => getJson<ApiStatus>('/api/status')
export const getHealth = () => getJson<HealthStatus>('/health')
export const getUser = (userId: number) => getJson<UserInfo>(`/api/users/${userId}`)

/**
 * Fetch analytics summary for a user.
 * Returns null when the backend has no analytics data
 * (it sends 200 with { message: "No analytics data available" } instead of the summary shape).
 */
export async function getAnalytics(userId: number): Promise<AnalyticsSummary | null> {
  const res = await apiFetch(`/api/users/${userId}/analytics`)
  if (!res.ok) throw await toError(res)
  const body = await res.json()
  // When no analytics exist the backend sends { message: "..." } instead of summary fields.
  if ('message' in body && !('total_posts_analyzed' in body)) return null
  return body as AnalyticsSummary
}

export interface UploadArgs {
  file: File
  userId: number
  onProgress?: (percent: number) => void
  signal?: AbortSignal
}

/**
 * Upload a reel via XMLHttpRequest.
 *
 * XHR rather than fetch() deliberately: fetch exposes no upload-progress
 * events, and progress feedback is a requirement for this flow
 * (docs/ARCHITECTURE.md, "Media Upload - Design Notes").
 */
export function uploadReel({
  file,
  userId,
  onProgress,
  signal,
}: UploadArgs): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('user_id', String(userId))
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/upload')

    // Must be set AFTER open() and BEFORE send(). Without it the upload is
    // anonymous and the API rejects it with 401 - which presents as a stalled
    // progress bar rather than an obvious failure, because the request is
    // refused only once the whole body has been transferred.
    const token = localStorage.getItem(SESSION_KEY)
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      let parsed: unknown
      try {
        parsed = JSON.parse(xhr.responseText)
      } catch {
        reject(new Error(`Unexpected response from server (${xhr.status})`))
        return
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(parsed as UploadResponse)
      } else {
        reject(new Error((parsed as ApiError)?.error ?? `Upload failed (${xhr.status})`))
      }
    }

    xhr.onerror = () => reject(new Error('Network error during upload'))
    xhr.ontimeout = () => reject(new Error('Upload timed out'))
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))

    signal?.addEventListener('abort', () => xhr.abort(), { once: true })

    xhr.send(form)
  })
}
