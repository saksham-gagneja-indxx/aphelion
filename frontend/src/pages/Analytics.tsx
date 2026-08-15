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
import { BTN_QUIET, EYEBROW, H1, H2, META } from '../ui'
import { useUserId } from '../current-user'

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function formatHour(hour: number): string {
  if (hour === 0) return '12 AM'
  if (hour === 12) return '12 PM'
  return hour < 12 ? `${hour} AM` : `${hour - 12} PM`
}

/**
 * `accent` is the one violet card in the grid — exactly one per grid.
 * Confidence owns it here.
 */
function MetricCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
}) {
  return (
    <div
      className={`border p-5 ${
        accent ? 'border-violet-500/50 bg-violet-900/40' : 'border-line bg-ink-900'
      }`}
    >
      <p className={`${EYEBROW} ${accent ? 'text-violet-200' : ''}`}>{label}</p>
      <p className="mt-4 font-display text-[32px] leading-none font-light tracking-[-.02em] text-mist-50">
        {value}
      </p>
      {sub && <p className={`${META} mt-2 ${accent ? 'text-violet-300/70' : ''}`}>{sub}</p>}
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  // Threshold logic is unchanged; with the palette down to violet/white/black
  // the three bands read as fill strength rather than hue.
  let color = 'border-line bg-ink-900 text-mist-500'
  if (confidence >= 70) color = 'border-violet-500/50 bg-violet-900 text-violet-200'
  else if (confidence >= 50) color = 'border-violet-500/40 bg-violet-500/[0.1] text-violet-300'

  return (
    <span className={`inline-flex items-center border px-3 py-1 text-[14px] ${color}`}>
      {confidence}% confidence
    </span>
  )
}

function AnalyticsData({ data }: { data: AnalyticsSummary }) {
  return (
    <>
      {/* Top-level metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
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
          accent
        />
      </div>

      {/* Best posting times */}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {/* Best hours */}
        <div className="surface p-5">
          <h3 className={H2}>Best Posting Hours</h3>
          {data.best_posting_hours.length > 0 ? (
            <ul className="mt-4 space-y-2.5">
              {data.best_posting_hours.map((hour, i) => (
                <li key={hour} className="flex items-center gap-3 text-[16px] text-mist-200">
                  <span
                    className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
                      i === 0 ? 'bg-violet-300' : i < 3 ? 'bg-violet-500' : 'bg-mist-500'
                    }`}
                  />
                  {formatHour(hour)}
                  {i === 0 && <span className={`${EYEBROW} ml-auto text-violet-300`}>Peak</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className={`${META} mt-4`}>No data yet</p>
          )}
        </div>

        {/* Best days */}
        <div className="surface p-5">
          <h3 className={H2}>Best Posting Days</h3>
          {data.best_posting_days.length > 0 ? (
            <ul className="mt-4 space-y-2.5">
              {data.best_posting_days.map((dayIndex, i) => (
                <li
                  key={dayIndex}
                  className="flex items-center gap-3 text-[16px] text-mist-200"
                >
                  <span
                    className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
                      i === 0 ? 'bg-violet-300' : 'bg-violet-500'
                    }`}
                  />
                  {DAY_NAMES[dayIndex] ?? `Day ${dayIndex}`}
                  {i === 0 && <span className={`${EYEBROW} ml-auto text-violet-300`}>Top</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className={`${META} mt-4`}>No data yet</p>
          )}
        </div>
      </div>

      {/* Peak hour + confidence badge + last updated */}
      <div className="mt-6 flex flex-wrap items-center gap-4 text-[16px] text-mist-500">
        {data.peak_engagement_hour != null && (
          <span>
            Peak engagement:{' '}
            <span className="text-mist-50">{formatHour(data.peak_engagement_hour)}</span>
          </span>
        )}
        <ConfidenceBadge confidence={data.confidence} />
        {data.last_updated && (
          <span className={`${META} ml-auto`}>
            Updated {new Date(data.last_updated).toLocaleDateString()}
          </span>
        )}
      </div>
    </>
  )
}

export default function Analytics() {
  const USER_ID = useUserId()
  const query = useQuery({
    queryKey: ['analytics', USER_ID],
    queryFn: () => getAnalytics(USER_ID),
  })

  return (
    <div className="mx-auto max-w-[880px] animate-rise-in">
      <div className="flex items-center justify-between gap-6">
        <h1 className={H1}>Analytics</h1>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className={`${BTN_QUIET} shrink-0`}
        >
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

      <div className="mt-8">
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
            message="No posts published yet — analytics will appear here once you publish."
          />
        )}

        {query.isSuccess && query.data != null && <AnalyticsData data={query.data} />}
      </div>
    </div>
  )
}
