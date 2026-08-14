import type { AnalyticsSummary, ApiError, ApiStatus, HealthStatus, UploadResponse, UserInfo } from './types'

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

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
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
  const res = await fetch(`/api/users/${userId}/analytics`)
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
