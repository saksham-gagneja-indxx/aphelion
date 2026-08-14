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
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold text-slate-900">Schedule a reel</h1>
      <p className="mt-1 text-sm text-slate-500">
        Pick an uploaded reel, add a caption, and choose when it should post.
      </p>

      {/* ---------- reel picker ---------- */}
      <section className="mt-6">
        <h2 className="text-sm font-medium text-slate-700">Uploaded reels</h2>

        {/* Branches below are exhaustive and mutually exclusive: error ->
            pending -> empty -> list. Note isPending (not isLoading): during
            retry backoff a query is pending with fetchStatus "idle", so
            isLoading is false and gating on it leaves a blank section. */}
        {!reelsQuery.isError && reelsQuery.isPending && (
          <p className="mt-2 text-sm text-slate-500">Loading reels&hellip;</p>
        )}

        {reelsQuery.isError && (
          <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-800">Could not load reels</p>
            <p className="mt-1 text-sm text-red-700">
              {(reelsQuery.error as Error).message}
            </p>
            {reels.length > 0 && (
              <p className="mt-1 text-xs text-red-600">
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
          <div className="mt-2 rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-600">
              No reels uploaded yet. Upload one first, then come back here to schedule it.
            </p>
          </div>
        )}

        {reels.length > 0 && (
          <ul className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {reels.map((reel) => {
              const isSelected = selected?.path === reel.path
              return (
                <li key={reel.path}>
                  <button
                    type="button"
                    onClick={() => setSelected(isSelected ? null : reel)}
                    className={`w-full overflow-hidden rounded-lg border-2 bg-white text-left transition ${
                      isSelected
                        ? 'border-indigo-500 ring-2 ring-indigo-200'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="aspect-[9/16] max-h-40 w-full overflow-hidden bg-slate-100">
                      {reel.has_thumbnail ? (
                        <img
                          src={thumbnailUrl(USER_ID, reel.filename)}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-xs text-slate-400">
                          no preview
                        </div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="truncate text-xs font-medium text-slate-700">
                        {reel.filename}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
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
      <form onSubmit={submit} className="mt-8 rounded-lg border border-slate-200 bg-white p-5">
        <label className="block text-sm font-medium text-slate-700" htmlFor="caption">
          Caption
        </label>
        <textarea
          id="caption"
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          rows={3}
          placeholder="Optional caption for the reel"
          className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm focus:border-indigo-500 focus:outline-none"
        />

        <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="when">
          Post at
        </label>
        <input
          id="when"
          type="datetime-local"
          value={when}
          min={minWhen}
          onChange={(e) => setWhen(e.target.value)}
          className="mt-1 rounded-md border border-slate-300 p-2 text-sm focus:border-indigo-500 focus:outline-none"
        />
        <p className="mt-1 text-xs text-slate-400">
          Interpreted in the account timezone configured on the backend.
        </p>

        <button
          type="submit"
          disabled={scheduleMutation.isPending}
          className="mt-5 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {scheduleMutation.isPending ? 'Scheduling…' : 'Schedule reel'}
        </button>

        {selected && (
          <p className="mt-3 truncate text-xs text-slate-500">
            Selected: {selected.filename}
          </p>
        )}

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}
        {notice && !error && (
          <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3">
            <p className="text-sm text-emerald-700">{notice}</p>
          </div>
        )}
      </form>

      {/* ---------- scheduled list ---------- */}
      <section className="mt-10">
        <h2 className="text-sm font-medium text-slate-700">
          Scheduled posts {jobs.length > 0 && `(${jobs.length})`}
        </h2>

        {!jobsQuery.isError && jobsQuery.isPending && (
          <p className="mt-2 text-sm text-slate-500">Loading&hellip;</p>
        )}

        {jobsQuery.isError && (
          <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-800">
              Could not load scheduled posts
            </p>
            <p className="mt-1 text-sm text-red-700">
              {(jobsQuery.error as Error).message}
            </p>
            {jobs.length > 0 && (
              <p className="mt-1 text-xs text-red-600">
                Showing the last known schedule — it may be out of date.
              </p>
            )}
          </div>
        )}

        {/* Same reasoning as the reels list: an outage must not render as
            "nothing scheduled". */}
        {jobsQuery.isSuccess && jobs.length === 0 && (
          <p className="mt-2 text-sm text-slate-500">Nothing scheduled yet.</p>
        )}

        {jobs.length > 0 && (
          <ul className="mt-2 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            {jobs.map((job) => (
              <li key={job.job_id ?? job.id} className="flex items-center justify-between p-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800">
                    {formatWhen(job.scheduled_time)}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-slate-500">
                    {job.caption || <span className="italic">no caption</span>}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => cancelMutation.mutate(job.id)}
                  disabled={cancelMutation.isPending}
                  className="ml-4 shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 transition hover:border-red-300 hover:text-red-600 disabled:opacity-50"
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
