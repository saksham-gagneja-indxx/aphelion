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

// Single local user for v1 - no auth, per docs/TIMELINE.md.
const USER_ID = 1

/** Section heading — the eyebrow label from the dark-glass type scale. */
const EYEBROW =
  'text-[11.5px] font-semibold uppercase tracking-[.16em] text-lilac-50/42'

/**
 * Thumbnail wash behind a reel that has no generated preview yet, cycled by
 * position so a grid of pending uploads doesn't read as one flat block.
 */
const REEL_TINTS = [
  'linear-gradient(150deg, rgba(170,59,255,.22), rgba(5,4,9,.6))',
  'linear-gradient(150deg, rgba(52,211,153,.16), rgba(5,4,9,.6))',
  'linear-gradient(150deg, rgba(96,165,250,.16), rgba(5,4,9,.6))',
]

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
      <h1 className="font-display text-[34px] leading-tight font-bold tracking-[-.03em] text-lilac-50">
        Schedule a reel
      </h1>
      <p className="mt-2 text-[14.5px] text-lilac-50/50">
        Pick an uploaded reel, add a caption, and choose when it should post.
      </p>

      {/* ---------- reel picker ---------- */}
      <section className="mt-[30px]">
        <h2 className={EYEBROW}>Uploaded reels</h2>

        {/* Branches below are exhaustive and mutually exclusive: error ->
            pending -> empty -> list. Note isPending (not isLoading): during
            retry backoff a query is pending with fetchStatus "idle", so
            isLoading is false and gating on it leaves a blank section. */}
        {!reelsQuery.isError && reelsQuery.isPending && (
          <p className="mt-3.5 text-[13.5px] text-lilac-50/45">Loading reels&hellip;</p>
        )}

        {reelsQuery.isError && (
          <div className="mt-3.5 rounded-xl border border-status-failed/[0.26] bg-status-failed/[0.09] px-[15px] py-[13px]">
            <p className="text-[13.5px] font-semibold text-[#FDA4AF]">Could not load reels</p>
            <p className="mt-[3px] text-[13px] text-[#FDA4AF]/80">
              {(reelsQuery.error as Error).message}
            </p>
            {reels.length > 0 && (
              <p className="mt-1 text-xs text-[#FDA4AF]/70">
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
          <div className="mt-3.5 rounded-xl border border-lilac-50/[0.08] bg-lilac-50/[0.03] p-4">
            <p className="text-[13.5px] text-lilac-50/62">
              No reels uploaded yet. Upload one first, then come back here to schedule it.
            </p>
          </div>
        )}

        {reels.length > 0 && (
          <ul className="mt-3.5 grid grid-cols-2 gap-3.5 sm:grid-cols-3">
            {reels.map((reel, i) => {
              const isSelected = selected?.path === reel.path
              return (
                <li key={reel.path}>
                  <button
                    type="button"
                    onClick={() => setSelected(isSelected ? null : reel)}
                    className={`w-full overflow-hidden rounded-[14px] border bg-lilac-50/[0.035] text-left backdrop-blur-[12px] transition ${
                      isSelected
                        ? 'border-violet-400 shadow-[0_0_0_3px_rgba(170,59,255,.18)]'
                        : 'border-lilac-50/[0.09] hover:border-lilac-50/20'
                    }`}
                  >
                    <div
                      className="flex h-[150px] w-full items-center justify-center overflow-hidden"
                      style={{ background: REEL_TINTS[i % REEL_TINTS.length] }}
                    >
                      {reel.has_thumbnail ? (
                        <img
                          src={thumbnailUrl(USER_ID, reel.filename)}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <svg
                          className="h-5 w-5 text-lilac-50/30"
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
                        className={`truncate text-[12.5px] font-semibold ${
                          isSelected ? 'text-lilac-50' : 'text-lilac-50/70'
                        }`}
                      >
                        {reel.filename}
                      </p>
                      <p className="mt-[3px] text-[11.5px] text-lilac-50/35">
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
      <form onSubmit={submit} className="glass mt-7 rounded-[18px] p-[22px]">
        <label className="block text-[13px] font-semibold text-lilac-50/78" htmlFor="caption">
          Caption
        </label>
        <textarea
          id="caption"
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          rows={3}
          placeholder="Optional caption for the reel"
          className="mt-2 min-h-[88px] w-full rounded-xl border border-lilac-50/10 bg-ink-950/50 px-3.5 py-3 text-[13.5px] text-lilac-50 transition placeholder:text-lilac-50/34 focus:border-violet-400 focus:bg-violet-400/[0.07] focus:shadow-[0_0_0_3px_rgba(170,59,255,.15)] focus:outline-none"
        />

        <label className="mt-5 block text-[13px] font-semibold text-lilac-50/78" htmlFor="when">
          Post at
        </label>
        <input
          id="when"
          type="datetime-local"
          value={when}
          min={minWhen}
          onChange={(e) => setWhen(e.target.value)}
          className="mt-2 rounded-xl border border-lilac-50/10 bg-ink-950/50 px-3.5 py-[11px] text-[13.5px] text-lilac-50 transition focus:border-violet-400 focus:bg-violet-400/[0.07] focus:shadow-[0_0_0_3px_rgba(170,59,255,.15)] focus:outline-none"
        />
        <p className="mt-2 text-xs text-lilac-50/35">
          Interpreted in the account timezone configured on the backend.
        </p>

        <button
          type="submit"
          disabled={scheduleMutation.isPending}
          className="mt-[22px] rounded-pill bg-[linear-gradient(180deg,#AA3BFF,#7E14FF)] px-6 py-3 text-sm font-semibold text-white shadow-glow transition hover:-translate-y-px hover:brightness-110 disabled:opacity-50 disabled:hover:translate-y-0"
        >
          {scheduleMutation.isPending ? 'Scheduling…' : 'Schedule reel'}
        </button>

        {selected && (
          <p className="mt-3.5 truncate text-xs text-lilac-50/42">
            Selected: {selected.filename}
          </p>
        )}

        {error && (
          <div className="mt-4 rounded-xl border border-status-failed/[0.26] bg-status-failed/[0.09] px-[15px] py-[13px]">
            <p className="text-[13.5px] text-[#FDA4AF]">{error}</p>
          </div>
        )}
        {notice && !error && (
          <div className="mt-4 rounded-xl border border-status-posted/[0.26] bg-status-posted/[0.09] px-[15px] py-[13px]">
            <p className="text-[13.5px] text-[#6EE7B7]">{notice}</p>
          </div>
        )}
      </form>

      {/* ---------- scheduled list ---------- */}
      <section className="mt-[38px]">
        <h2 className={EYEBROW}>
          Scheduled posts {jobs.length > 0 && `(${jobs.length})`}
        </h2>

        {!jobsQuery.isError && jobsQuery.isPending && (
          <p className="mt-3.5 text-[13.5px] text-lilac-50/45">Loading&hellip;</p>
        )}

        {jobsQuery.isError && (
          <div className="mt-3.5 rounded-xl border border-status-failed/[0.26] bg-status-failed/[0.09] px-[15px] py-[13px]">
            <p className="text-[13.5px] font-semibold text-[#FDA4AF]">
              Could not load scheduled posts
            </p>
            <p className="mt-[3px] text-[13px] text-[#FDA4AF]/80">
              {(jobsQuery.error as Error).message}
            </p>
            {jobs.length > 0 && (
              <p className="mt-1 text-xs text-[#FDA4AF]/70">
                Showing the last known schedule — it may be out of date.
              </p>
            )}
          </div>
        )}

        {/* Same reasoning as the reels list: an outage must not render as
            "nothing scheduled". */}
        {jobsQuery.isSuccess && jobs.length === 0 && (
          <p className="mt-3.5 text-[13.5px] text-lilac-50/45">Nothing scheduled yet.</p>
        )}

        {jobs.length > 0 && (
          <ul className="mt-3.5 divide-y divide-lilac-50/[0.07] overflow-hidden rounded-2xl border border-lilac-50/[0.09] bg-lilac-50/[0.035] backdrop-blur-[20px]">
            {jobs.map((job) => (
              <li
                key={job.job_id ?? job.id}
                className="flex items-center justify-between px-[18px] py-4"
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-lilac-50/88">
                    {formatWhen(job.scheduled_time)}
                  </p>
                  <p className="mt-1 truncate text-[12.5px] text-lilac-50/45">
                    {job.caption || <span className="italic text-lilac-50/35">no caption</span>}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => cancelMutation.mutate(job.id)}
                  disabled={cancelMutation.isPending}
                  className="ml-4 shrink-0 rounded-[9px] border border-lilac-50/[0.16] px-3.5 py-[7px] text-[12.5px] text-lilac-50/60 transition hover:border-status-failed/50 hover:text-status-failed disabled:opacity-50"
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
