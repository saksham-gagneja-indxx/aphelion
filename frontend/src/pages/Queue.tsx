/**
 * Queue page — built by the antigravity session.
 *
 * Shows all posts (newest first), with status pills, thumbnails, captions,
 * scheduled times, and prominently surfaces error details for failed posts.
 *
 * Filterable by status. Cancel button on scheduled posts.
 * Uses the exhaustive isPending/isError/isSuccess+empty branch pattern.
 *
 * Surface treatment: dark glass v1. Structure, copy and behaviour are
 * unchanged from the light build — only the skin differs.
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

/**
 * One row per PostStatus. `hex` is the dot colour — it also tints the
 * thumbnail gradient, which is the only place the raw value is needed.
 */
const STATUS_CONFIG: Record<
  PostStatus,
  { label: string; hex: string; dot: string; pill: string }
> = {
  draft: {
    label: 'Draft',
    hex: '#94A3B8',
    dot: 'bg-status-draft',
    pill: 'bg-status-draft/[0.13] text-[#CBD5E1] border-status-draft/30',
  },
  queued: {
    label: 'Queued',
    hex: '#60A5FA',
    dot: 'bg-status-queued',
    pill: 'bg-status-queued/[0.13] text-[#93C5FD] border-status-queued/30',
  },
  scheduled: {
    label: 'Scheduled',
    hex: '#AA3BFF',
    dot: 'bg-status-scheduled',
    pill: 'bg-status-scheduled/[0.16] text-[#C9A9FF] border-status-scheduled/[0.32]',
  },
  posted: {
    label: 'Posted',
    hex: '#34D399',
    dot: 'bg-status-posted',
    pill: 'bg-status-posted/[0.13] text-[#6EE7B7] border-status-posted/30',
  },
  failed: {
    label: 'Failed',
    hex: '#FB7185',
    dot: 'bg-status-failed',
    pill: 'bg-status-failed/[0.12] text-[#FDA4AF] border-status-failed/[0.32]',
  },
  cancelled: {
    label: 'Cancelled',
    hex: '#FBBF24',
    dot: 'bg-status-cancelled',
    pill: 'bg-status-cancelled/[0.12] text-[#FCD34D] border-status-cancelled/30',
  },
}

function StatusPill({ status }: { status: PostStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.draft
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-[3px] text-[11.5px] font-semibold ${cfg.pill}`}
    >
      <span className={`inline-block h-[5px] w-[5px] rounded-full ${cfg.dot}`} />
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
  const cfg = STATUS_CONFIG[post.status] ?? STATUS_CONFIG.draft

  return (
    <li
      className={`overflow-hidden rounded-2xl border backdrop-blur-[20px] transition-transform duration-200 hover:-translate-y-0.5 ${
        isFailed
          ? 'border-status-failed/[0.28] bg-status-failed/[0.05] shadow-[0_8px_30px_rgba(251,113,133,.08)]'
          : 'border-lilac-50/[0.09] bg-lilac-50/[0.035] shadow-[0_8px_30px_rgba(0,0,0,.3)]'
      }`}
    >
      <div className="flex gap-4 p-4">
        {/* Thumbnail */}
        <div
          className="flex h-20 w-14 shrink-0 items-center justify-center overflow-hidden rounded-[10px] border border-lilac-50/10"
          style={{
            background: `linear-gradient(150deg, ${cfg.hex}38, rgba(134,59,255,.10))`,
          }}
        >
          {post.thumbnail_path ? (
            <img
              src={thumbnailUrl(USER_ID, post.thumbnail_path)}
              alt=""
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <svg
              className="h-5 w-5 text-lilac-50/35"
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
          <div className="flex items-center gap-2.5">
            <StatusPill status={post.status} />
            {post.video_duration != null && (
              <span className="text-xs text-lilac-50/35">{post.video_duration.toFixed(1)}s</span>
            )}
            {isScheduled && (
              <button
                type="button"
                onClick={() => onCancel(post.id)}
                disabled={isCancelling}
                className="ml-auto shrink-0 rounded-lg border border-lilac-50/[0.16] px-[11px] py-[5px] text-xs text-lilac-50/60 transition hover:border-status-failed/50 hover:text-status-failed disabled:opacity-50"
              >
                {isCancelling ? 'Cancelling…' : 'Cancel'}
              </button>
            )}
          </div>

          <p className="mt-2.5 line-clamp-2 text-sm leading-relaxed text-lilac-50/80">
            {post.caption || <span className="italic text-lilac-50/35">No caption</span>}
          </p>

          <div className="mt-2.5 flex flex-wrap items-center gap-x-[18px] gap-y-1 text-xs text-lilac-50/35">
            {post.scheduled_time && (
              <span>
                Scheduled: <span className="text-lilac-50/62">{formatWhen(post.scheduled_time)}</span>
              </span>
            )}
            {post.posted_at && (
              <span>
                Posted: <span className="text-lilac-50/62">{formatWhen(post.posted_at)}</span>
              </span>
            )}
            <span>
              Created: <span className="text-lilac-50/62">{formatWhen(post.created_at)}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Error details — prominent for FAILED posts */}
      {isFailed && (
        <div className="flex items-start gap-2.5 border-t border-status-failed/[0.22] bg-status-failed/[0.09] px-4 py-3.5">
          <svg
            className="mt-px h-[17px] w-[17px] shrink-0 text-status-failed"
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
            <p className="text-[13.5px] font-semibold text-[#FDA4AF]">
              Posting failed
              {retryCount > 0 && (
                <span className="ml-2 font-normal text-[#FDA4AF]/70">
                  ({retryCount} {retryCount === 1 ? 'retry' : 'retries'})
                </span>
              )}
            </p>
            {errorMessage && (
              <p className="mt-[3px] text-[13.5px] break-words text-[#FDA4AF]/85">{errorMessage}</p>
            )}
            {!errorMessage && (
              <p className="mt-[3px] text-[13.5px] italic text-[#FDA4AF]/70">
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
    <div className="mx-auto max-w-[820px] animate-rise-in">
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-display text-[34px] leading-tight font-bold tracking-[-.03em] text-lilac-50">
            Post Queue
          </h1>
          <p className="mt-2 text-[14.5px] text-lilac-50/50">
            Track every post from draft to published — or find out why it failed.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="inline-flex shrink-0 items-center gap-2 rounded-[10px] border border-lilac-50/[0.14] bg-lilac-50/[0.06] px-[15px] py-[9px] text-[13.5px] font-semibold whitespace-nowrap text-lilac-50 backdrop-blur-[12px] transition hover:bg-lilac-50/[0.12]"
        >
          <svg
            className="h-[15px] w-[15px]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
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
        <div className="mt-6 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`rounded-pill border px-3.5 py-1.5 text-[12.5px] font-semibold transition ${
              filter === 'all'
                ? 'border-lilac-50/[0.92] bg-lilac-50/[0.92] text-ink-900'
                : 'border-lilac-50/10 bg-lilac-50/5 text-lilac-50/60 hover:bg-lilac-50/10'
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
                className={`rounded-pill border px-3.5 py-1.5 text-[12.5px] font-semibold transition ${
                  filter === s
                    ? cfg.pill
                    : 'border-lilac-50/10 bg-lilac-50/5 text-lilac-50/60 hover:bg-lilac-50/10'
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
        <div className="mt-4 rounded-xl border border-status-failed/[0.26] bg-status-failed/[0.09] px-[15px] py-[13px]">
          <p className="text-[13.5px] text-[#FDA4AF]">
            Cancel failed: {(cancelMutation.error as Error).message}
          </p>
        </div>
      )}

      {/* Mutation success */}
      {cancelMutation.isSuccess && (
        <div className="mt-4 rounded-xl border border-status-posted/[0.26] bg-status-posted/[0.09] px-[15px] py-[13px]">
          <p className="text-[13.5px] text-[#6EE7B7]">Post cancelled successfully.</p>
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
              <p className="py-8 text-center text-[13.5px] text-lilac-50/45">
                No {filter} posts. Try a different filter.
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
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
