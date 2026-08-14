// Client-side pre-validation. Mirrors the server rules in
// backend/core/reel_manager.py so obviously-bad files are rejected before a
// long upload starts. The server still re-validates - this is UX, not security.

export const ALLOWED_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv', 'webm'] as const
export const MAX_UPLOAD_BYTES = 500 * 1024 * 1024 // matches MAX_UPLOAD_SIZE in .env
export const MAX_DURATION_SECONDS = 90 // Instagram reel limit

export function extensionOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i === -1 ? '' : name.slice(i + 1).toLowerCase()
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** Synchronous checks - extension and size. Returns null when the file passes. */
export function validateFile(file: File): string | null {
  const ext = extensionOf(file.name)
  if (!ALLOWED_EXTENSIONS.includes(ext as (typeof ALLOWED_EXTENSIONS)[number])) {
    return `Unsupported file type ".${ext || 'unknown'}". Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
  }
  if (file.size === 0) {
    return 'File is empty'
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File is ${formatBytes(file.size)}, which exceeds the ${formatBytes(MAX_UPLOAD_BYTES)} limit`
  }
  return null
}

/**
 * Read duration via a detached <video> element.
 * Resolves null when the browser can't decode the container (e.g. mkv/avi) -
 * that's not a failure, it just means we defer to server-side ffprobe.
 */
export function readDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    video.preload = 'metadata'

    const done = (value: number | null) => {
      URL.revokeObjectURL(url)
      resolve(value)
    }

    video.onloadedmetadata = () => {
      const d = video.duration
      done(Number.isFinite(d) && d > 0 ? d : null)
    }
    video.onerror = () => done(null)
    // Don't let a stuck decode block the upload indefinitely.
    setTimeout(() => done(null), 5000)

    video.src = url
  })
}

/** Full pre-flight check including duration where the browser can read it. */
export async function preflight(file: File): Promise<string | null> {
  const basic = validateFile(file)
  if (basic) return basic

  const duration = await readDuration(file)
  if (duration !== null && duration > MAX_DURATION_SECONDS) {
    return `Video is ${duration.toFixed(1)}s, which exceeds the ${MAX_DURATION_SECONDS}s reel limit`
  }
  return null
}
