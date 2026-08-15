import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelPost,
  createPost,
  listReels,
  listScheduledJobs,
  schedulePost,
  thumbnailUrl,
} from '../api/schedule'
import { formatBytes } from '../api/validation'
import type { Reel } from '../api/types'
import {
  BANNER_DANGER,
  BANNER_OK,
  BANNER_QUIET,
  BTN_PRIMARY,
  EYEBROW,
  FIELD,
  H1,
  LABEL,
  META,
  SUB,
} from '../ui'

// Single local user for v1 - no auth, per docs/TIMELINE.md.
const USER_ID = 1

/** Local datetime string for <input type="datetime-local">, minutes precision. */
function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

function formatWhen(iso: string | null): string {
  if (!iso) return 'unscheduled'
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

export default function Schedule() {
  const queryClient = useQueryClient()

  const [selected, setSelected] = useState<Reel | null>(null)
  const [caption, setCaption] = useState('')
  const [when, setWhen] = useState(() =>
    toLocalInputValue(new Date(Date.now() + 15 * 60 * 1000)),
  )
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const reelsQuery = useQuery({
    queryKey: ['reels', USER_ID],
    queryFn: () => listReels(USER_ID),
  })

  const jobsQuery = useQuery({
    queryKey: ['scheduledJobs', USER_ID],
    queryFn: () => listScheduledJobs(USER_ID),
    refetchInterval: 30_000,
  })

  const minWhen = useMemo(() => toLocalInputValue(new Date()), [])

  const scheduleMutation = useMutation({
    // Two calls: the API creates a draft post from the reel, then schedules it.
    mutationFn: async () => {
      if (!selected) throw new Error('Pick a reel first')
      const post = await createPost({
        userId: USER_ID,
        videoPath: selected.path,
        caption: caption.trim() || undefined,
      })
      return schedulePost(post.id, when)
    },
    onSuccess: (res) => {
      setNotice(`Scheduled for ${formatWhen(res.post.scheduled_time)}`)
      setError(null)
      setSelected(null)
      setCaption('')
      queryClient.invalidateQueries({ queryKey: ['scheduledJobs', USER_ID] })
    },
    onError: (err: Error) => {
      setError(err.message)
      setNotice(null)
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (postId: number) => cancelPost(postId),
    onSuccess: () => {
      setNotice('Scheduled post cancelled')
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['scheduledJobs', USER_ID] })
    },
    onError: (err: Error) => setError(err.message),
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setNotice(null)

    if (!selected) {
      setError('Pick a reel to schedule')
      return
    }
    if (!when) {
      setError('Pick a date and time')
      return
    }
    // Mirror the server rule so the user gets feedback without a round trip.
    if (new Date(when).getTime() <= Date.now()) {
      setError('Scheduled time must be in the future')
      return
    }
    scheduleMutation.mutate()
  }

  const reels = reelsQuery.data?.reels ?? []
  const jobs = jobsQuery.data?.jobs ?? []

  return (
    <div className="mx-auto max-w-3xl animate-rise-in">
      <h1 className={H1}>Schedule a reel</h1>
      <p className={SUB}>Pick an uploaded reel, add a caption, and choose when it should post.</p>

      {/* ---------- reel picker ---------- */}
      <section className="mt-10">
        <h2 className={EYEBROW}>Uploaded reels</h2>

        {/* Branches below are exhaustive and mutually exclusive: error ->
            pending -> empty -> list. Note isPending (not isLoading): during
            retry backoff a query is pending with fetchStatus "idle", so
            isLoading is false and gating on it leaves a blank section. */}
        {!reelsQuery.isError && reelsQuery.isPending && (
          <p className="mt-4 text-[16px] text-mist-500">Loading reels&hellip;</p>
        )}

        {reelsQuery.isError && (
          <div className={`${BANNER_DANGER} mt-4`}>
            <p className="text-[16px] text-danger-soft">Could not load reels</p>
            <p className="mt-1 text-[15px] text-danger-soft/70">
              {(reelsQuery.error as Error).message}
            </p>
            {reels.length > 0 && (
              <p className="mt-1 text-[14px] text-danger-soft/60">
                Showing the last known list — it may be out of date.
              </p>
            )}
          </div>
        )}

        {/* Only claim "nothing uploaded" on a SUCCESSFUL empty response. A
            failed fetch also yields an empty list, and reporting that as
            "no reels" tells the user their uploads are gone when the backend
            is merely unreachable. */}
        {reelsQuery.isSuccess && reels.length === 0 && (
          <div className={`${BANNER_QUIET} mt-4`}>
            <p className="text-[16px] text-mist-500">
              No reels uploaded yet. Upload one first, then come back here to schedule it.
            </p>
          </div>
        )}

        {reels.length > 0 && (
          <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {reels.map((reel) => {
              const isSelected = selected?.path === reel.path
              return (
                <li key={reel.path}>
                  <button
                    type="button"
                    onClick={() => setSelected(isSelected ? null : reel)}
                    /* Background lives in both branches, never in the base:
                       two bg-* utilities on one element resolve by CSS source
                       order, not by the order they appear in the attribute. */
                    className={`w-full border text-left transition ${
                      isSelected
                        ? 'border-violet-500 bg-violet-500/[0.06]'
                        : 'border-line bg-ink-900 hover:border-mist-500'
                    }`}
                  >
                    <div className="flex h-[150px] w-full items-center justify-center overflow-hidden bg-ink-800">
                      {reel.has_thumbnail ? (
                        <img
                          src={thumbnailUrl(USER_ID, reel.filename)}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <svg
                          className="h-5 w-5 text-mist-500"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={1.5}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25z"
                          />
                        </svg>
                      )}
                    </div>
                    <div className="px-3 py-2.5">
                      <p
                        className={`truncate text-[15px] ${
                          isSelected ? 'text-mist-50' : 'text-mist-200'
                        }`}
                      >
                        {reel.filename}
                      </p>
                      <p className={`${META} mt-1`}>
                        {reel.duration_seconds != null
                          ? `${reel.duration_seconds.toFixed(1)}s`
                          : 'unknown'}{' '}
                        &middot; {formatBytes(reel.size_bytes)}
                      </p>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {/* ---------- schedule form ---------- */}
      <form onSubmit={submit} className="surface mt-8 p-6">
        <label className={LABEL} htmlFor="caption">
          Caption
        </label>
        <textarea
          id="caption"
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          rows={3}
          placeholder="Optional caption for the reel"
          className={`${FIELD} mt-2 min-h-[96px]`}
        />

        <label className={`${LABEL} mt-6`} htmlFor="when">
          Post at
        </label>
        <input
          id="when"
          type="datetime-local"
          value={when}
          min={minWhen}
          onChange={(e) => setWhen(e.target.value)}
          className={`${FIELD} mt-2`}
        />
        <p className={`${META} mt-2`}>
          Interpreted in the account timezone configured on the backend.
        </p>

        <button
          type="submit"
          disabled={scheduleMutation.isPending}
          className={`${BTN_PRIMARY} mt-7`}
        >
          {scheduleMutation.isPending ? 'Scheduling…' : 'Schedule reel'}
        </button>

        {selected && (
          <p className={`${META} mt-4 truncate`}>Selected: {selected.filename}</p>
        )}

        {error && (
          <div className={`${BANNER_DANGER} mt-6`}>
            <p className="text-[15px] text-danger-soft">{error}</p>
          </div>
        )}
        {notice && !error && (
          <div className={`${BANNER_OK} mt-6`}>
            <p className="text-[15px] text-violet-200">{notice}</p>
          </div>
        )}
      </form>

      {/* ---------- scheduled list ---------- */}
      <section className="mt-12">
        <h2 className={EYEBROW}>
          Scheduled posts {jobs.length > 0 && `(${jobs.length})`}
        </h2>

        {!jobsQuery.isError && jobsQuery.isPending && (
          <p className="mt-4 text-[16px] text-mist-500">Loading&hellip;</p>
        )}

        {jobsQuery.isError && (
          <div className={`${BANNER_DANGER} mt-4`}>
            <p className="text-[16px] text-danger-soft">Could not load scheduled posts</p>
            <p className="mt-1 text-[15px] text-danger-soft/70">
              {(jobsQuery.error as Error).message}
            </p>
            {jobs.length > 0 && (
              <p className="mt-1 text-[14px] text-danger-soft/60">
                Showing the last known schedule — it may be out of date.
              </p>
            )}
          </div>
        )}

        {/* Same reasoning as the reels list: an outage must not render as
            "nothing scheduled". */}
        {jobsQuery.isSuccess && jobs.length === 0 && (
          <p className="mt-4 text-[16px] text-mist-500">Nothing scheduled yet.</p>
        )}

        {jobs.length > 0 && (
          <ul className="surface mt-4 divide-y divide-line">
            {jobs.map((job) => (
              <li
                key={job.job_id ?? job.id}
                className="flex items-center justify-between px-5 py-4"
              >
                <div className="min-w-0">
                  <p className="text-[16px] text-mist-50">{formatWhen(job.scheduled_time)}</p>
                  <p className={`${META} mt-1 truncate`}>
                    {job.caption || <span className="italic">no caption</span>}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => cancelMutation.mutate(job.id)}
                  disabled={cancelMutation.isPending}
                  className="ml-4 shrink-0 border border-line px-3.5 py-1.5 text-[14px] text-mist-500 transition hover:border-danger/50 hover:text-danger disabled:opacity-40"
                >
                  Cancel
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
