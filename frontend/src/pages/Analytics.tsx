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

/**
 * `accent` is the one violet card in the grid — exactly one per grid, per the
 * dark-glass spec. Confidence owns it here.
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
      className={`rounded-2xl border p-5 backdrop-blur-[20px] ${
        accent
          ? 'border-violet-400/[0.26] bg-[linear-gradient(180deg,rgba(170,59,255,.14),rgba(237,230,255,.03))] shadow-[0_8px_30px_rgba(134,59,255,.14)]'
          : 'border-lilac-50/[0.09] bg-lilac-50/[0.04] shadow-[0_8px_30px_rgba(0,0,0,.3)]'
      }`}
    >
      <p
        className={`text-[11px] font-semibold uppercase tracking-[.14em] ${
          accent ? 'text-lilac-300/70' : 'text-lilac-50/40'
        }`}
      >
        {label}
      </p>
      <p className="mt-2.5 font-display text-[30px] leading-none font-bold tracking-[-.03em] text-lilac-50">
        {value}
      </p>
      {sub && (
        <p className={`mt-1.5 text-[11.5px] ${accent ? 'text-lilac-300/55' : 'text-lilac-50/32'}`}>
          {sub}
        </p>
      )}
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  // Threshold logic is unchanged — only the palette moved to dark glass.
  let color = 'bg-status-failed/[0.12] text-[#FDA4AF] border-status-failed/[0.3]'
  if (confidence >= 70) color = 'bg-status-posted/[0.13] text-[#6EE7B7] border-status-posted/30'
  else if (confidence >= 50)
    color = 'bg-status-cancelled/[0.12] text-[#FCD34D] border-status-cancelled/30'

  return (
    <span
      className={`inline-flex items-center rounded-pill border px-3 py-1 text-xs font-semibold ${color}`}
    >
      {confidence}% confidence
    </span>
  )
}

function AnalyticsData({ data }: { data: AnalyticsSummary }) {
  return (
    <>
      {/* Top-level metrics */}
      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
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
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {/* Best hours */}
        <div className="rounded-2xl border border-lilac-50/[0.09] bg-lilac-50/[0.04] p-5 backdrop-blur-[20px]">
          <h3 className="text-sm font-semibold text-lilac-50">Best Posting Hours</h3>
          {data.best_posting_hours.length > 0 ? (
            <ul className="mt-4 space-y-2.5">
              {data.best_posting_hours.map((hour, i) => (
                <li key={hour} className="flex items-center gap-2.5 text-[13.5px] text-lilac-50/78">
                  <span
                    className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                      i === 0
                        ? 'bg-status-posted'
                        : i < 3
                          ? 'bg-status-posted/50'
                          : 'bg-lilac-50/20'
                    }`}
                  />
                  {formatHour(hour)}
                  {i === 0 && (
                    <span className="ml-auto text-[11.5px] font-semibold text-[#6EE7B7]">Peak</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-[13.5px] text-lilac-50/35">No data yet</p>
          )}
        </div>

        {/* Best days */}
        <div className="rounded-2xl border border-lilac-50/[0.09] bg-lilac-50/[0.04] p-5 backdrop-blur-[20px]">
          <h3 className="text-sm font-semibold text-lilac-50">Best Posting Days</h3>
          {data.best_posting_days.length > 0 ? (
            <ul className="mt-4 space-y-2.5">
              {data.best_posting_days.map((dayIndex, i) => (
                <li
                  key={dayIndex}
                  className="flex items-center gap-2.5 text-[13.5px] text-lilac-50/78"
                >
                  <span
                    className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                      i === 0 ? 'bg-violet-400' : 'bg-violet-400/50'
                    }`}
                  />
                  {DAY_NAMES[dayIndex] ?? `Day ${dayIndex}`}
                  {i === 0 && (
                    <span className="ml-auto text-[11.5px] font-semibold text-lilac-300">Top</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-[13.5px] text-lilac-50/35">No data yet</p>
          )}
        </div>
      </div>

      {/* Peak hour + confidence badge + last updated */}
      <div className="mt-[22px] flex flex-wrap items-center gap-4 text-[13.5px] text-lilac-50/50">
        {data.peak_engagement_hour != null && (
          <span>
            Peak engagement:{' '}
            <span className="font-semibold text-lilac-50/[0.82]">
              {formatHour(data.peak_engagement_hour)}
            </span>
          </span>
        )}
        <ConfidenceBadge confidence={data.confidence} />
        {data.last_updated && (
          <span className="ml-auto text-xs text-lilac-50/32">
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
    <div className="mx-auto max-w-[820px] animate-rise-in">
      <div className="flex items-center justify-between gap-6">
        <h1 className="font-display text-[34px] leading-tight font-bold tracking-[-.03em] text-lilac-50">
          Analytics
        </h1>
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

      <div className="mt-[26px]">
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
