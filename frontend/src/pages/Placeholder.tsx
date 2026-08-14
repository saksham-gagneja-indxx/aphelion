/**
 * Deliberate stub for pages not yet built (Schedule, Analytics, Settings).
 * Renders an explicit "not built yet" state so a half-finished page can't be
 * mistaken for a broken one - docs/TIMELINE.md hour 21-23 calls for
 * half-built surfaces to fail loud rather than silently.
 */
export default function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
        <p className="text-sm font-medium text-amber-900">Not built yet</p>
        <p className="mt-1 text-sm text-amber-800">{note}</p>
      </div>
    </div>
  )
}
