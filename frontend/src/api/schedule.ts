// Scheduling API surface.
//
// Kept separate from client.ts deliberately: that file is being edited
// concurrently by the session building Analytics/Settings.
//
// Shapes verified against live responses from backend/api/routes.py.

import type { ApiError, Reel } from './types'

/** GET /api/users/:id/reels */
export interface ReelsResponse {
  count: number
  reels: Reel[]
}

/** A post row as returned by Post.to_dict(). */
export interface Post {
  id: number
  user_id: number
  video_path: string
  thumbnail_path: string | null
  video_duration: number | null
  job_id: string | null
  caption: string | null
  hashtags: string | null
  status: 'draft' | 'queued' | 'scheduled' | 'posted' | 'failed' | 'cancelled'
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
}

/** One entry from GET /api/scheduler/jobs - a slimmer projection than Post. */
export interface ScheduledJob {
  id: number
  user_id: number
  caption: string | null
  scheduled_time: string | null
  job_id: string | null
  platform: string
}

export interface ScheduledJobsResponse {
  count: number
  jobs: ScheduledJob[]
}

export interface ScheduleResponse {
  success: true
  job_id: string
  post: Post
}

import { apiFetch } from './auth'

async function toError(res: Response): Promise<Error> {
  try {
    const body = (await res.json()) as ApiError
    if (body?.error) return new Error(body.error)
  } catch {
    // non-JSON body
  }
  return new Error(`Request failed (${res.status} ${res.statusText})`)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // apiFetch, not fetch: every /api/* route requires a bearer token. A plain
  // fetch here returns 401, which surfaced as "Could not load reels" and
  // "Could not load scheduled posts" on the Schedule page.
  const res = await apiFetch(path, init)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as T
}

const jsonInit = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const listReels = (userId: number) =>
  request<ReelsResponse>(`/api/users/${userId}/reels`)

export const listScheduledJobs = (userId: number) =>
  request<ScheduledJobsResponse>(`/api/scheduler/jobs?user_id=${userId}`)

export const createPost = (input: {
  userId: number
  videoPath: string
  caption?: string
  /** Explicit so a backend default can never silently pick a disabled platform. */
  platform?: 'linkedin' | 'instagram'
}) =>
  request<Post>(
    '/api/posts',
    jsonInit('POST', {
      user_id: input.userId,
      video_path: input.videoPath,
      caption: input.caption || null,
      platform: input.platform ?? 'linkedin',
    }),
  )

/**
 * `scheduledTime` is a naive local ISO string (what <input type="datetime-local">
 * produces). The backend localises it to the user's configured timezone.
 */
export const schedulePost = (postId: number, scheduledTime: string) =>
  request<ScheduleResponse>(
    `/api/posts/${postId}/schedule`,
    jsonInit('POST', { scheduled_time: scheduledTime }),
  )

export const cancelPost = (postId: number) =>
  request<{ success: boolean; message: string }>(`/api/posts/${postId}`, {
    method: 'DELETE',
  })

export interface PublishResponse {
  message: string
  post: Post
  url: string
  platform_post_id: string
}

/**
 * Publish immediately, bypassing the schedule.
 *
 * Slow by nature: LinkedIn transcodes the video before the post can be
 * created, so this can take tens of seconds. Callers must show progress rather
 * than appearing frozen.
 */
export const publishNow = (postId: number) =>
  request<PublishResponse>(`/api/posts/${postId}/publish`, { method: 'POST' })

/** Retract a published post from the platform. */
export const deletePublished = (postId: number) =>
  request<{ message: string; post: Post }>(`/api/posts/${postId}/published`, {
    method: 'DELETE',
  })

/** Reels are stored on the server; thumbnails are served through the API. */
export const thumbnailUrl = (userId: number, filename: string) =>
  `/api/users/${userId}/reels/${encodeURIComponent(filename)}/thumbnail`
