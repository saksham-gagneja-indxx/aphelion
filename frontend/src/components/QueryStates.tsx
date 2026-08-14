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

/** Red error banner — backend unreachable or endpoint failure. */
export function QueryError({
  title,
  message,
}: {
  title: string
  message?: string
}) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4">
      <p className="text-sm font-medium text-red-800">{title}</p>
      {message && <p className="mt-1 text-sm text-red-700">{message}</p>}
    </div>
  )
}

/** Loading / pending indicator. */
export function QueryPending({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
      <p className="text-sm text-slate-500">{label}</p>
    </div>
  )
}

/** Amber empty-state banner — only render when isSuccess is true. */
export function QueryEmpty({
  title,
  message,
}: {
  title: string
  message?: string
}) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
      <p className="text-sm font-medium text-amber-900">{title}</p>
      {message && <p className="mt-1 text-sm text-amber-800">{message}</p>}
    </div>
  )
}
