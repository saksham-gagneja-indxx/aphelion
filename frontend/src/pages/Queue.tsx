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
  deletePost,
  getPosts,
  thumbnailUrl,
  type Post,
  type PostStatus,
} from '../api/queue'
import { QueryError, QueryPending, QueryEmpty } from '../components/QueryStates'
import { useUserId } from '../current-user'
import { useUndo } from '../undo'
import { BANNER_DANGER, BANNER_OK, BTN_QUIET, H1, META, SUB } from '../ui'

const ALL_STATUSES: PostStatus[] = ['draft', 'queued', 'scheduled', 'posted', 'failed', 'cancelled']

/**
 * Six states in violet, white and black.
 *
 * With colour coding gone the load moves to fill and border: violet intensity
 * climbs draft → scheduled → posted, cancelled takes a dashed rule to read as
 * "stopped" rather than "not started", and failed keeps a hue of its own
 * because a broken post is the one thing this screen exists to surface.
 */
const STATUS_CONFIG: Record<PostStatus, { label: string; dot: string; pill: string }> = {
  draft: {
    label: 'Draft',
    dot: 'bg-mist-500',
    pill: 'border-line bg-ink-900 text-mist-500',
  },
  queued: {
    label: 'Queued',
    dot: 'bg-mist-200',
    pill: 'border-line bg-ink-900 text-mist-200',
  },
  scheduled: {
    label: 'Scheduled',
    dot: 'bg-violet-500',
    pill: 'border-violet-500/45 bg-violet-500/[0.12] text-violet-300',
  },
  posted: {
    label: 'Posted',
    dot: 'bg-violet-300',
    pill: 'border-violet-500/50 bg-violet-900 text-violet-200',
  },
  failed: {
    label: 'Failed',
    dot: 'bg-danger',
    pill: 'border-danger/45 bg-danger/[0.1] text-danger-soft',
  },
  cancelled: {
    label: 'Cancelled',
    dot: 'bg-mist-500',
    pill: 'border-dashed border-mist-500/60 bg-transparent text-mist-500',
  },
}

function StatusPill({ status }: { status: PostStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.draft
  return (
    <span className={`inline-flex items-center gap-2 border px-2.5 py-0.5 text-[13px] ${cfg.pill}`}>
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
  onDelete,
  isCancelling,
}: {
  post: Post
  onCancel: (id: number) => void
  onDelete: (post: Post) => void
  isCancelling: boolean
}) {
  const USER_ID = useUserId()
  const isFailed = post.status === 'failed'
  const isScheduled = post.status === 'scheduled'
  const errorMessage = post.error_message
  const retryCount = post.retry_count ?? 0

  return (
    <li
      className={`border transition-colors ${
        isFailed ? 'border-danger/40 bg-danger/[0.04]' : 'border-line bg-ink-900 hover:bg-ink-800'
      }`}
    >
      <div className="flex gap-5 p-5">
        {/* Thumbnail */}
        <div className="flex h-20 w-14 shrink-0 items-center justify-center overflow-hidden border border-line bg-ink-800">
          {post.thumbnail_path ? (
            <img
              src={thumbnailUrl(USER_ID, post.thumbnail_path)}
              alt=""
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <svg
              className="h-5 w-5 text-mist-500"
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
          )}
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <StatusPill status={post.status} />
            <span className="inline-flex items-center border border-line bg-ink-800 px-2.5 py-0.5 text-[13px] text-mist-500 capitalize">
              {post.platform}
            </span>
            {post.video_duration != null && (
              <span className={META}>{post.video_duration.toFixed(1)}s</span>
            )}
            <span className="ml-auto flex shrink-0 items-center gap-2">
              {isScheduled && (
                <button
                  type="button"
                  onClick={() => onCancel(post.id)}
                  disabled={isCancelling}
                  className="border border-line px-3 py-1 text-[14px] text-mist-500 transition hover:border-danger/50 hover:text-danger disabled:opacity-40"
                >
                  {isCancelling ? 'Cancelling…' : 'Cancel'}
                </button>
              )}
              {/* No confirm dialog: the 15-second undo window is the
                  confirmation, and it does not interrupt anyone who meant it. */}
              <button
                type="button"
                onClick={() => onDelete(post)}
                aria-label="Delete post"
                title="Delete post"
                className="border border-line p-1.5 text-mist-500 transition hover:border-danger/50 hover:text-danger"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
                </svg>
              </button>
            </span>
          </div>

          <p className="mt-3 line-clamp-2 text-[16px] leading-[1.5] text-mist-50">
            {post.caption || <span className="text-mist-500 italic">No caption</span>}
          </p>

          <div className={`${META} mt-3 flex flex-wrap items-center gap-x-6 gap-y-1`}>
            {post.scheduled_time && (
              <span>
                Scheduled: <span className="text-mist-200">{formatWhen(post.scheduled_time)}</span>
              </span>
            )}
            {post.posted_at && (
              <span>
                Posted: <span className="text-mist-200">{formatWhen(post.posted_at)}</span>
              </span>
            )}
            <span>
              Created: <span className="text-mist-200">{formatWhen(post.created_at)}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Error details — prominent for FAILED posts */}
      {isFailed && (
        <div className="flex items-start gap-3 border-t border-danger/30 bg-danger/[0.07] px-5 py-4">
          <svg className="mt-0.5 h-[18px] w-[18px] shrink-0 text-danger" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
              clipRule="evenodd"
            />
          </svg>
          <div className="min-w-0">
            <p className="text-[15px] text-danger-soft">
              Posting failed
              {retryCount > 0 && (
                <span className="ml-2 text-danger-soft/60">
                  ({retryCount} {retryCount === 1 ? 'retry' : 'retries'})
                </span>
              )}
            </p>
            {errorMessage && (
              <p className="mt-1 text-[15px] break-words text-danger-soft/75">{errorMessage}</p>
            )}
            {!errorMessage && (
              <p className="mt-1 text-[15px] text-danger-soft/60 italic">
                No error details available — check backend logs.
              </p>
            )}
          </div>
        </div>
      )}
    </li>
  )
}

export default function Queue() {
  const USER_ID = useUserId()
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

  const { pendingKeys, scheduleDelete } = useUndo()

  const handleDelete = (post: Post) => {
    scheduleDelete({
      key: `post:${post.id}`,
      label: post.caption?.trim()
        ? `Deleted “${post.caption.trim().slice(0, 40)}”`
        : 'Post deleted',
      commit: (init) => deletePost(post.id, init),
      // Refetch either way: on commit the row is gone, and on undo the list
      // still needs to stop hiding it.
      onSettled: () => {
        queryClient.invalidateQueries({ queryKey: ['posts', USER_ID] })
        queryClient.invalidateQueries({ queryKey: ['scheduledJobs', USER_ID] })
      },
    })
  }

  const posts = (query.data?.posts ?? []).filter(
    // Hidden immediately so the delete feels instant, but not yet sent.
    (p) => !pendingKeys.has(`post:${p.id}`),
  )
  const filtered = (filter === 'all' ? posts : posts.filter((p) => p.status === filter)).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  // Count per status for filter badges
  const counts = posts.reduce<Partial<Record<PostStatus, number>>>((acc, p) => {
    acc[p.status] = (acc[p.status] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="mx-auto max-w-[880px] animate-rise-in">
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className={H1}>Post Queue</h1>
          <p className={SUB}>Track every post from draft to published — or find out why it failed.</p>
        </div>
        <button type="button" onClick={() => void query.refetch()} className={`${BTN_QUIET} shrink-0`}>
          <svg
            className="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.6}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 12a9 9 0 1 1-2.64-6.36" />
            <path d="M21 3v6h-6" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Status filter pills */}
      {query.isSuccess && posts.length > 0 && (
        <div className="mt-8 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`border px-3.5 py-1.5 text-[14px] transition ${
              filter === 'all'
                ? 'border-mist-50 bg-mist-50 text-ink-950'
                : 'border-line bg-ink-900 text-mist-500 hover:text-mist-50'
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
                className={`border px-3.5 py-1.5 text-[14px] transition ${
                  filter === s ? cfg.pill : 'border-line bg-ink-900 text-mist-500 hover:text-mist-50'
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
        <div className={`${BANNER_DANGER} mt-6`}>
          <p className="text-[15px] text-danger-soft">
            Cancel failed: {(cancelMutation.error as Error).message}
          </p>
        </div>
      )}

      {/* Mutation success */}
      {cancelMutation.isSuccess && (
        <div className={`${BANNER_OK} mt-6`}>
          <p className="text-[15px] text-violet-200">Post cancelled successfully.</p>
        </div>
      )}

      {/* Query state branches: error → pending → empty → data */}
      <div className="mt-8">
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
              <p className="py-10 text-center text-[16px] text-mist-500">
                No {filter} posts. Try a different filter.
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {filtered.map((post) => (
                  <PostCard
                    key={post.id}
                    post={post}
                    onCancel={(id) => cancelMutation.mutate(id)}
                    onDelete={handleDelete}
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
