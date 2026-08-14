/**
 * Analytics page — built by the antigravity session (Hour 12–18 sprint).
 * Error-state hardening: Hour 21–23 (antigravity session).
 *
 * Calls GET /api/users/1/analytics and displays key metrics:
 *   - Posts analyzed
 *   - Average likes / comments
 *   - Confidence %
 *   - Best posting hours / days
 *
 * Query-state branches are exhaustive and mutually exclusive:
 *   isError → isPending → isSuccess+null → isSuccess+data
 *
 * Uses isPending (not isLoading) to avoid a blank section during retry
 * backoff, and gates the empty state on isSuccess so a dead backend never
 * renders as "No analytics data available".
 */
import { useQuery } from '@tanstack/react-query'
import { getAnalytics } from '../api/client'
import { QueryError, QueryPending, QueryEmpty } from '../components/QueryStates'
import type { AnalyticsSummary } from '../api/types'

const USER_ID = 1

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function formatHour(hour: number): string {
  if (hour === 0) return '12 AM'
  if (hour === 12) return '12 PM'
  return hour < 12 ? `${hour} AM` : `${hour - 12} PM`
}

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  let color = 'bg-red-100 text-red-800'
  if (confidence >= 70) color = 'bg-emerald-100 text-emerald-800'
  else if (confidence >= 50) color = 'bg-amber-100 text-amber-800'

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      {confidence}% confidence
    </span>
  )
}

function AnalyticsData({ data }: { data: AnalyticsSummary }) {
  return (
    <>
      {/* Top-level metrics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricCard
          label="Posts Analyzed"
          value={data.total_posts_analyzed}
        />
        <MetricCard
          label="Avg Likes"
          value={data.average_likes != null ? data.average_likes.toFixed(1) : '—'}
          sub="per post"
        />
        <MetricCard
          label="Avg Comments"
          value={data.average_comments != null ? data.average_comments.toFixed(1) : '—'}
          sub="per post"
        />
        <MetricCard
          label="Confidence"
          value={`${data.confidence}%`}
          sub="recommendation quality"
        />
      </div>

      {/* Best posting times */}
      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        {/* Best hours */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">Best Posting Hours</h3>
          {data.best_posting_hours.length > 0 ? (
            <ul className="mt-3 space-y-1.5">
              {data.best_posting_hours.map((hour, i) => (
                <li key={hour} className="flex items-center gap-2 text-sm text-slate-700">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      i === 0 ? 'bg-emerald-500' : i < 3 ? 'bg-emerald-300' : 'bg-slate-300'
                    }`}
                  />
                  {formatHour(hour)}
                  {i === 0 && (
                    <span className="ml-auto text-xs text-emerald-600 font-medium">Peak</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No data yet</p>
          )}
        </div>

        {/* Best days */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">Best Posting Days</h3>
          {data.best_posting_days.length > 0 ? (
            <ul className="mt-3 space-y-1.5">
              {data.best_posting_days.map((dayIndex, i) => (
                <li key={dayIndex} className="flex items-center gap-2 text-sm text-slate-700">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      i === 0 ? 'bg-indigo-500' : 'bg-indigo-300'
                    }`}
                  />
                  {DAY_NAMES[dayIndex] ?? `Day ${dayIndex}`}
                  {i === 0 && (
                    <span className="ml-auto text-xs text-indigo-600 font-medium">Top</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No data yet</p>
          )}
        </div>
      </div>

      {/* Peak hour + confidence badge + last updated */}
      <div className="mt-6 flex flex-wrap items-center gap-4 text-sm text-slate-500">
        {data.peak_engagement_hour != null && (
          <span>
            Peak engagement:{' '}
            <span className="font-medium text-slate-700">{formatHour(data.peak_engagement_hour)}</span>
          </span>
        )}
        <ConfidenceBadge confidence={data.confidence} />
        {data.last_updated && (
          <span className="ml-auto text-xs text-slate-400">
            Updated {new Date(data.last_updated).toLocaleDateString()}
          </span>
        )}
      </div>
    </>
  )
}

export default function Analytics() {
  const query = useQuery({
    queryKey: ['analytics', USER_ID],
    queryFn: () => getAnalytics(USER_ID),
  })

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Analytics</h1>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      <div className="mt-6">
        {/* Exhaustive, mutually exclusive branches: error → pending → empty → data.
            Order matters: isError first so a dead backend never falls through to
            the empty state that reads "No analytics data available". */}

        {query.isError && (
          <QueryError
            title="Failed to load analytics"
            message={(query.error as Error).message}
          />
        )}

        {/* isPending, not isLoading: during retry backoff the query is pending
            with fetchStatus "idle", so isLoading is false and gating on it
            leaves a completely blank section. */}
        {!query.isError && query.isPending && (
          <QueryPending label="Loading analytics…" />
        )}

        {/* Gate on isSuccess: a failed fetch also yields null data, and showing
            "No analytics data" would be lying about a dead backend. */}
        {query.isSuccess && query.data == null && (
          <QueryEmpty
            title="No analytics data available"
            message="Connect your Instagram account and run an engagement analysis to see insights here."
          />
        )}

        {query.isSuccess && query.data != null && <AnalyticsData data={query.data} />}
      </div>
    </div>
  )
}
