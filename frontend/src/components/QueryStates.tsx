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

/** Rose error banner — backend unreachable or endpoint failure. */
export function QueryError({
  title,
  message,
}: {
  title: string
  message?: string
}) {
  return (
    <div className="rounded-xl border border-status-failed/[0.26] bg-status-failed/[0.09] px-[15px] py-[13px]">
      <p className="text-[13.5px] font-semibold text-[#FDA4AF]">{title}</p>
      {message && <p className="mt-[3px] text-[13px] text-[#FDA4AF]/80">{message}</p>}
    </div>
  )
}

/** Loading / pending indicator. */
export function QueryPending({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="rounded-xl border border-lilac-50/[0.08] bg-lilac-50/[0.03] p-5 text-center text-[13.5px] text-lilac-50/45">
      {label}
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
    <div className="rounded-xl border border-status-cancelled/[0.24] bg-status-cancelled/[0.08] p-[18px] text-center">
      <p className="text-[13.5px] font-semibold text-[#FCD34D]">{title}</p>
      {message && <p className="mt-[3px] text-[13px] text-[#FCD34D]/[0.78]">{message}</p>}
    </div>
  )
}
