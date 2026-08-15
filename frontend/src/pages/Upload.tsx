import { useCallback, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadReel } from '../api/client'
import { formatBytes, preflight } from '../api/validation'
import type { Reel } from '../api/types'
import { BANNER_DANGER, BANNER_QUIET, BTN_DANGER, H1, META, SUB } from '../ui'

// Single local user for v1 - no auth, per docs/TIMELINE.md.
const USER_ID = 1

type Phase = 'idle' | 'checking' | 'uploading' | 'done' | 'error'

export default function Upload() {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const [phase, setPhase] = useState<Phase>('idle')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [uploaded, setUploaded] = useState<Reel | null>(null)
  const [dragging, setDragging] = useState(false)

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      const controller = new AbortController()
      abortRef.current = controller
      return uploadReel({
        file,
        userId: USER_ID,
        onProgress: setProgress,
        signal: controller.signal,
      })
    },
    onSuccess: (res) => {
      setUploaded(res.reel)
      setPhase('done')
      queryClient.invalidateQueries({ queryKey: ['reels', USER_ID] })
    },
    onError: (err: Error) => {
      // A user-initiated cancel isn't an error state worth shouting about.
      if (err.name === 'AbortError') {
        setPhase('idle')
        setProgress(0)
        return
      }
      setError(err.message)
      setPhase('error')
    },
  })

  const handleFile = useCallback(
    async (file: File) => {
      setError(null)
      setUploaded(null)
      setProgress(0)
      setPhase('checking')

      const problem = await preflight(file)
      if (problem) {
        setError(problem)
        setPhase('error')
        return
      }

      setPhase('uploading')
      mutation.mutate(file)
    },
    [mutation],
  )

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) void handleFile(file)
  }

  const busy = phase === 'checking' || phase === 'uploading'

  return (
    <div className="mx-auto max-w-2xl animate-rise-in">
      <h1 className={H1}>Upload a reel</h1>
      <p className={SUB}>
        MP4, MOV, AVI, MKV or WEBM &middot; up to 90 seconds &middot; max 500&nbsp;MB
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !busy && inputRef.current?.click()}
        className={[
          'relative mt-8 flex h-[260px] cursor-pointer flex-col items-center justify-center border border-dashed transition',
          dragging
            ? 'border-violet-500 bg-violet-500/[0.06]'
            : 'border-line bg-ink-900 hover:border-violet-500 hover:bg-violet-500/[0.04]',
          busy ? 'pointer-events-none opacity-50' : '',
        ].join(' ')}
      >
        <svg
          className="h-10 w-10 text-violet-500"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.2}
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9m0 0L8.25 12.75M12 9l3.75 3.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        <p className="mt-5 text-[18px] text-mist-50">
          Drop a video here, or <span className="text-violet-300">browse</span>
        </p>
        <p className={`${META} mt-2`}>Validated locally before upload starts</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".mp4,.mov,.avi,.mkv,.webm,video/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void handleFile(file)
          // Reset so re-picking the same file fires onChange again.
          e.target.value = ''
        }}
      />

      {phase === 'checking' && (
        <p className="mt-6 text-[16px] text-mist-500">Checking file&hellip;</p>
      )}

      {phase === 'uploading' && (
        <div className={`${BANNER_QUIET} mt-6`}>
          <div className="flex items-center justify-between text-[15px] text-mist-200">
            <span>Uploading&hellip; {progress}%</span>
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="text-mist-500 underline transition hover:text-mist-50"
            >
              Cancel
            </button>
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden bg-ink-800">
            <div
              className="h-full animate-shimmer bg-[linear-gradient(90deg,#48008C,#8A05FF,#C29EFF)] bg-[length:260px_100%] transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          {progress === 100 && (
            <p className={`${META} mt-3`}>
              Transfer complete &mdash; server is validating and generating a thumbnail&hellip;
            </p>
          )}
        </div>
      )}

      {phase === 'error' && error && (
        <div className={`${BANNER_DANGER} mt-6`}>
          <p className="text-[16px] text-danger-soft">Upload failed</p>
          <p className="mt-1 text-[15px] text-danger-soft/75">{error}</p>
          {/* Destructive is always outlined — nothing red is ever a fill. */}
          <button
            type="button"
            onClick={() => {
              setPhase('idle')
              setError(null)
            }}
            className={`${BTN_DANGER} mt-4`}
          >
            Try again
          </button>
        </div>
      )}

      {phase === 'done' && uploaded && (
        <div className="mt-6 border border-line border-l-2 border-l-violet-500 bg-ink-900 px-5 py-4">
          <p className="text-[16px] text-mist-50">Uploaded</p>
          <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-8 gap-y-2 text-[15px]">
            <dt className="text-mist-500">File</dt>
            <dd className="truncate text-mist-50">{uploaded.filename}</dd>
            <dt className="text-mist-500">Duration</dt>
            <dd className="text-mist-50">
              {uploaded.duration_seconds != null
                ? `${uploaded.duration_seconds.toFixed(1)}s`
                : 'unknown'}
            </dd>
            <dt className="text-mist-500">Size</dt>
            <dd className="text-mist-50">{formatBytes(uploaded.size_bytes)}</dd>
            <dt className="text-mist-500">Thumbnail</dt>
            <dd className="text-mist-50">{uploaded.has_thumbnail ? 'generated' : 'pending'}</dd>
          </dl>
        </div>
      )}
    </div>
  )
}
