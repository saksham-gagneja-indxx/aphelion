/**
 * Shared query-state components for consistent error and empty handling.
 *
 * Every page should branch on query state in this exact order:
 *   1. isError   → <QueryError>
 *   2. isPending → <QueryPending>
 *   3. isSuccess + empty data → <QueryEmpty>
 *   4. isSuccess + data → render data
 *
 * Why isPending instead of isLoading:
 *   During retry backoff a query is pending with fetchStatus "idle", so
 *   isLoading (= isPending && fetchStatus "fetching") is false — gating a
 *   spinner on isLoading leaves a completely blank section. The main session
 *   already found and fixed this in Schedule.tsx.
 *
 * Why gate empty states on isSuccess:
 *   When the backend is down, data defaults (null, []) look identical to
 *   genuine empty results. "No analytics data" and "Not connected" are
 *   valid backend answers — but they must never render when the backend
 *   is simply unreachable.
 */

import { BANNER_DANGER, BANNER_QUIET } from '../ui'

/** Error banner — backend unreachable or endpoint failure. */
export function QueryError({
  title,
  message,
}: {
  title: string
  message?: string
}) {
  return (
    <div className={BANNER_DANGER}>
      <p className="text-[16px] text-danger-soft">{title}</p>
      {message && <p className="mt-1 text-[15px] text-danger-soft/70">{message}</p>}
    </div>
  )
}

/** Loading / pending indicator. */
export function QueryPending({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="surface px-4 py-8 text-center text-[16px] text-mist-500">{label}</div>
  )
}

/**
 * Empty state — only render when isSuccess is true. Violet-edged rather than
 * amber: nothing is wrong here, there is simply nothing yet.
 */
export function QueryEmpty({
  title,
  message,
}: {
  title: string
  message?: string
}) {
  return (
    <div className={`${BANNER_QUIET} border-l-2 border-l-violet-500 py-6 text-center`}>
      <p className="text-[16px] text-mist-50">{title}</p>
      {message && <p className="mt-1 text-[15px] text-mist-500">{message}</p>}
    </div>
  )
}
