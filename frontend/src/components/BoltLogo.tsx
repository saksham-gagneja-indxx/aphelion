/** Wordmark: the supplied logo image, served from public/. */
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
    <img
      src="/logo.png"
      alt=""
      width={width}
      height={height}
      className={`block object-contain ${className}`}
    />
  )
}
