/**
 * Wordmark icon: a calendar (the thing being scheduled) with motion lines
 * trailing it (the automation). Replaces the earlier bolt, which read as
 * "fast" but not as "this app schedules posts".
 *
 * The calendar body uses currentColor so it inherits mist-50/violet-500 like
 * any icon in this system; the motion lines are fixed at violet-500 — they
 * are a brand mark rather than a status indicator, so they do not follow
 * `text-*` the way the calendar does.
 */
export default function BoltLogo({
  width = 22,
  height = 20,
  className = '',
}: {
  width?: number
  height?: number
  className?: string
}) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 124 116"
      fill="none"
      aria-hidden="true"
      className={`block ${className}`}
    >
      {/* Motion lines, tapering front-to-back like the reference mark. */}
      <rect x="0" y="49" width="47" height="10" rx="5" fill="#8A05FF" />
      <rect x="24" y="68" width="47" height="10" rx="5" fill="#8A05FF" />
      <rect x="33" y="87" width="35" height="10" rx="5" fill="#8A05FF" />

      {/* Calendar body. */}
      <rect x="52" y="27" width="72" height="82" rx="14" fill="currentColor" />
      <rect x="63" y="52" width="50" height="46" rx="6" fill="black" />
      <rect x="70" y="59" width="12" height="12" rx="3" fill="currentColor" />
      <rect x="88" y="59" width="12" height="12" rx="3" fill="currentColor" />
      <rect x="106" y="59" width="12" height="12" rx="3" fill="currentColor" />
      <rect x="70" y="76" width="12" height="12" rx="3" fill="currentColor" />
      <rect x="88" y="76" width="12" height="12" rx="3" fill="currentColor" />
      <rect x="106" y="76" width="12" height="12" rx="3" fill="currentColor" />

      {/* Binder tabs. */}
      <rect x="70" y="0" width="12" height="34" rx="6" fill="currentColor" />
      <rect x="106" y="0" width="12" height="34" rx="6" fill="currentColor" />
    </svg>
  )
}
