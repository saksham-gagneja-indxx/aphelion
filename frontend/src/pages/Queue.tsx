/**
 * Queue page — built by the antigravity session.
 *
 * Shows all posts (newest first), with status pills, thumbnails, captions,
 * scheduled times, and prominently surfaces error details for failed posts.
 *
 * Filterable by status. Cancel button on scheduled posts.
 * Uses the exhaustive isPending/isError/isSuccess+empty branch pattern.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelPost,
  getPosts,
  thumbnailUrl,
  type Post,
  type PostStatus,
} from '../api/queue'
import { QueryError, QueryPending, QueryEmpty } from '../components/QueryStates'

const USER_ID = 1

const ALL_STATUSES: PostStatus[] = ['draft', 'queued', 'scheduled', 'posted', 'failed', 'cancelled']

const STATUS_CONFIG: Record<PostStatus, { label: string; bg: string; text: string; dot: string }> = {
  draft:     { label: 'Draft',     bg: 'bg-slate-100',   text: 'text-slate-700',   dot: 'bg-slate-400' },
  queued:    { label: 'Queued',    bg: 'bg-blue-100',    text: 'text-blue-800',    dot: 'bg-blue-500' },
  scheduled: { label: 'Scheduled', bg: 'bg-indigo-100',  text: 'text-indigo-800',  dot: 'bg-indigo-500' },
  posted:    { label: 'Posted',    bg: 'bg-emerald-100', text: 'text-emerald-800', dot: 'bg-emerald-500' },
  failed:    { label: 'Failed',    bg: 'bg-red-100',     text: 'text-red-800',     dot: 'bg-red-500' },
  cancelled: { label: 'Cancelled', bg: 'bg-amber-100',   text: 'text-amber-800',   dot: 'bg-amber-500' },
}

function StatusPill({ status }: { status: PostStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.draft
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.bg} ${cfg.text}`}
    >
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

function formatWhen(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function PostCard({
  post,
  onCancel,
  isCancelling,
}: {
  post: Post
  onCancel: (id: number) => void
  isCancelling: boolean
}) {
  const isFailed = post.status === 'failed'
  const isScheduled = post.status === 'scheduled'
  const errorMessage = post.error_message
  const retryCount = post.retry_count ?? 0

  return (
    <li
      className={`rounded-lg border bg-white shadow-sm transition ${
        isFailed ? 'border-red-300 ring-1 ring-red-100' : 'border-slate-200'
      }`}
    >
      <div className="flex gap-4 p-4">
        {/* Thumbnail */}
        <div className="h-20 w-14 shrink-0 overflow-hidden rounded-md bg-slate-100">
          {post.thumbnail_path ? (
            <img
              src={thumbnailUrl(USER_ID, post.thumbnail_path)}
              alt=""
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <svg
                className="h-5 w-5 text-slate-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25z"
                />
              </svg>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <StatusPill status={post.status} />
            {post.video_duration != null && (
              <span className="text-xs text-slate-400">{post.video_duration.toFixed(1)}s</span>
            )}
            {isScheduled && (
              <button
                type="button"
                onClick={() => onCancel(post.id)}
                disabled={isCancelling}
                className="ml-auto shrink-0 rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-600 transition hover:border-red-300 hover:text-red-600 disabled:opacity-50"
              >
                {isCancelling ? 'Cancelling…' : 'Cancel'}
              </button>
            )}
          </div>

          <p className="mt-1.5 text-sm text-slate-700 line-clamp-2">
            {post.caption || <span className="italic text-slate-400">No caption</span>}
          </p>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            {post.scheduled_time && (
              <span>
                Scheduled: <span className="text-slate-600">{formatWhen(post.scheduled_time)}</span>
              </span>
            )}
            {post.posted_at && (
              <span>
                Posted: <span className="text-slate-600">{formatWhen(post.posted_at)}</span>
              </span>
            )}
            <span>
              Created: <span className="text-slate-600">{formatWhen(post.created_at)}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Error details — prominent for FAILED posts */}
      {isFailed && (
        <div className="border-t border-red-200 bg-red-50 px-4 py-3">
          <div className="flex items-start gap-2">
            <svg
              className="mt-0.5 h-4 w-4 shrink-0 text-red-500"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                clipRule="evenodd"
              />
            </svg>
            <div className="min-w-0">
              <p className="text-sm font-medium text-red-800">
                Posting failed
                {retryCount > 0 && (
                  <span className="ml-2 font-normal text-red-600">
                    ({retryCount} {retryCount === 1 ? 'retry' : 'retries'})
                  </span>
                )}
              </p>
              {errorMessage && (
                <p className="mt-0.5 text-sm text-red-700 break-words">{errorMessage}</p>
              )}
              {!errorMessage && (
                <p className="mt-0.5 text-sm text-red-600 italic">
                  No error details available — check backend logs.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </li>
  )
}

export default function Queue() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<PostStatus | 'all'>('all')

  const query = useQuery({
    queryKey: ['posts', USER_ID],
    queryFn: () => getPosts(USER_ID),
    // Poll every 30s so failed/posted transitions show up quickly
    refetchInterval: 30_000,
  })

  const cancelMutation = useMutation({
    mutationFn: (postId: number) => cancelPost(postId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts', USER_ID] })
      // Also invalidate the Schedule page's job list
      queryClient.invalidateQueries({ queryKey: ['scheduledJobs', USER_ID] })
    },
  })

  const posts = query.data?.posts ?? []
  const filtered = (filter === 'all' ? posts : posts.filter((p) => p.status === filter)).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  // Count per status for filter badges
  const counts = posts.reduce<Partial<Record<PostStatus, number>>>((acc, p) => {
    acc[p.status] = (acc[p.status] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Post Queue</h1>
          <p className="mt-1 text-sm text-slate-500">
            Track every post from draft to published — or find out why it failed.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      {/* Status filter pills */}
      {query.isSuccess && posts.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filter === 'all'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All ({posts.length})
          </button>
          {ALL_STATUSES.filter((s) => (counts[s] ?? 0) > 0).map((s) => {
            const cfg = STATUS_CONFIG[s]
            return (
              <button
                key={s}
                type="button"
                onClick={() => setFilter(s)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  filter === s
                    ? `${cfg.bg} ${cfg.text} ring-1 ring-current`
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {cfg.label} ({counts[s]})
              </button>
            )
          })}
        </div>
      )}

      {/* Mutation error */}
      {cancelMutation.isError && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3">
          <p className="text-sm text-red-700">
            Cancel failed: {(cancelMutation.error as Error).message}
          </p>
        </div>
      )}

      {/* Mutation success */}
      {cancelMutation.isSuccess && (
        <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3">
          <p className="text-sm text-emerald-700">Post cancelled successfully.</p>
        </div>
      )}

      {/* Query state branches: error → pending → empty → data */}
      <div className="mt-6">
        {query.isError && (
          <QueryError
            title="Could not load posts"
            message={(query.error as Error).message}
          />
        )}

        {!query.isError && query.isPending && (
          <QueryPending label="Loading posts…" />
        )}

        {query.isSuccess && posts.length === 0 && (
          <QueryEmpty
            title="No posts yet"
            message="Upload a reel and schedule it — it will appear here."
          />
        )}

        {query.isSuccess && posts.length > 0 && (
          <>
            {filtered.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-500">
                No {filter} posts. Try a different filter.
              </p>
            ) : (
              <ul className="space-y-3">
                {filtered.map((post) => (
                  <PostCard
                    key={post.id}
                    post={post}
                    onCancel={(id) => cancelMutation.mutate(id)}
                    isCancelling={cancelMutation.isPending}
                  />
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  )
}
