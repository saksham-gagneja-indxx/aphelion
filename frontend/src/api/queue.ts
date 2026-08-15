/**
 * API layer for the Queue page — owned by the antigravity session.
 *
 * Separate from api/client.ts and api/schedule.ts (owned by the main session).
 * Types are defined inline here rather than extending api/types.ts.
 */

// ---------- Types ----------

export type PostStatus = 'draft' | 'queued' | 'scheduled' | 'posted' | 'failed' | 'cancelled'

export interface Post {
  id: number
  user_id: number
  video_path: string
  thumbnail_path: string | null
  video_duration: number | null
  job_id: string | null
  caption: string | null
  hashtags: string | null
  status: PostStatus
  platform: string
  scheduled_time: string | null
  posted_at: string | null
  views: number
  likes: number
  comments: number
  shares: number
  engagement_rate: number | null
  created_at: string
  updated_at: string
  // These exist on the model but may not be serialised yet — handle undefined.
  error_message?: string | null
  retry_count?: number
}

export interface PostsResponse {
  count: number
  posts: Post[]
}

// ---------- Fetch helpers ----------

import { apiFetch, API_BASE } from './auth'

async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json()
    if (body?.error) return new Error(body.error)
  } catch { /* non-JSON */ }
  return new Error(`Request failed (${res.status} ${res.statusText})`)
}

async function getJson<T>(path: string): Promise<T> {
  const res = await apiFetch(path)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as T
}

async function postJson<T>(path: string): Promise<T> {
  const res = await apiFetch(path, { method: 'POST' })
  if (!res.ok) throw await toError(res)
  return (await res.json()) as T
}

// ---------- API functions ----------

export function getPosts(userId: number): Promise<PostsResponse> {
  return getJson<PostsResponse>(`/api/users/${userId}/posts`)
}

export function cancelPost(postId: number): Promise<{ message: string }> {
  return postJson<{ message: string }>(`/api/posts/${postId}/cancel`)
}

/**
 * Build a thumbnail URL.
 *
 * thumbnail_path from the backend is a relative filesystem path like
 * "data\\reels\\1\\file.jpg"; the route wants user_id + filename.
 *
 * Two corrections here. The path was /api/thumbnails/:user_id/:filename, which
 * no backend route ever served - the real one is under /users - so every Queue
 * thumbnail 404'd. And it needs API_BASE like every other URL, or a split
 * frontend/backend deploy resolves it against the frontend's own origin.
 */
export function thumbnailUrl(userId: number, thumbnailPath: string): string {
  // Extract just the filename from the path (handles both / and \\ separators)
  const filename = thumbnailPath.split(/[/\\]/).pop() ?? thumbnailPath
  return `${API_BASE}/api/users/${userId}/reels/${encodeURIComponent(filename)}/thumbnail`
}
