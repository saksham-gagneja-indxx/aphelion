/** Wordmark: the supplied logo image, served from public/. */
export default function BoltLogo({
  width = 40,
  height = 36,
  className = '',
}: {
  width?: number
  height?: number
  className?: string
}) {
  return (
    <img
      src="/logo.png"
      alt=""
      width={width}
      height={height}
      className={`block object-contain ${className}`}
    />
  )
}
