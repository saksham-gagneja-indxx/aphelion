import { useCallback, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadReel } from '../api/client'
import { formatBytes, preflight } from '../api/validation'
import type { Reel } from '../api/types'

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
      <h1 className="font-display text-[34px] leading-tight font-bold tracking-[-.03em] text-lilac-50">
        Upload a reel
      </h1>
      <p className="mt-2 text-[14.5px] text-lilac-50/50">
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
          'relative mt-[26px] flex h-[248px] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-[18px] border-2 border-dashed backdrop-blur-[12px] transition',
          dragging
            ? 'border-violet-400 bg-violet-400/[0.06]'
            : 'border-lilac-50/[0.16] bg-lilac-50/[0.03] hover:border-violet-400 hover:bg-violet-400/[0.06]',
          busy ? 'pointer-events-none opacity-60' : '',
        ].join(' ')}
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background: 'radial-gradient(50% 60% at 50% 45%, rgba(134,59,255,.14), transparent 70%)',
          }}
        />
        <svg
          className="relative h-[42px] w-[42px] text-violet-400"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.4}
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9m0 0L8.25 12.75M12 9l3.75 3.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        <p className="relative mt-4 text-[14.5px] font-medium text-lilac-50/[0.82]">
          Drop a video here, or <span className="font-semibold text-lilac-300">browse</span>
        </p>
        <p className="relative mt-1.5 text-[12.5px] text-lilac-50/38">
          Validated locally before upload starts
        </p>
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
        <p className="mt-4 text-[13.5px] text-lilac-50/62">Checking file&hellip;</p>
      )}

      {phase === 'uploading' && (
        <div className="mt-6 rounded-[14px] border border-lilac-50/[0.08] bg-lilac-50/[0.03] p-[18px]">
          <div className="flex items-center justify-between text-[13px] text-lilac-50/60">
            <span>Uploading&hellip; {progress}%</span>
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="text-lilac-50/45 underline transition hover:text-lilac-50"
            >
              Cancel
            </button>
          </div>
          <div className="mt-[9px] h-[7px] w-full overflow-hidden rounded-pill bg-lilac-50/[0.07]">
            <div
              className="h-full animate-shimmer rounded-pill bg-[linear-gradient(90deg,#7E14FF,#AA3BFF,#C9A9FF)] bg-[length:260px_100%] transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          {progress === 100 && (
            <p className="mt-[9px] text-xs text-lilac-50/35">
              Transfer complete &mdash; server is validating and generating a thumbnail&hellip;
            </p>
          )}
        </div>
      )}

      {phase === 'error' && error && (
        <div className="mt-6 rounded-[14px] border border-status-failed/[0.28] bg-status-failed/[0.07] p-[18px]">
          <p className="text-sm font-semibold text-[#FDA4AF]">Upload failed</p>
          <p className="mt-[5px] text-sm text-[#FDA4AF]/85">{error}</p>
          {/* The one legal red gradient button in the system — everywhere else
              destructive is the outlined variant. */}
          <button
            type="button"
            onClick={() => {
              setPhase('idle')
              setError(null)
            }}
            className="mt-3.5 rounded-pill bg-[linear-gradient(180deg,#FB7185,#E11D48)] px-[18px] py-[9px] text-[13.5px] font-semibold text-white shadow-[0_4px_18px_rgba(251,113,133,.3)] transition hover:brightness-110"
          >
            Try again
          </button>
        </div>
      )}

      {phase === 'done' && uploaded && (
        <div className="mt-6 rounded-[14px] border border-status-posted/[0.26] bg-status-posted/[0.07] p-[18px]">
          <p className="text-sm font-semibold text-[#6EE7B7]">Uploaded</p>
          <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[13.5px]">
            <dt className="text-lilac-50/50">File</dt>
            <dd className="truncate font-semibold text-lilac-50">{uploaded.filename}</dd>
            <dt className="text-lilac-50/50">Duration</dt>
            <dd className="font-semibold text-lilac-50">
              {uploaded.duration_seconds != null
                ? `${uploaded.duration_seconds.toFixed(1)}s`
                : 'unknown'}
            </dd>
            <dt className="text-lilac-50/50">Size</dt>
            <dd className="font-semibold text-lilac-50">{formatBytes(uploaded.size_bytes)}</dd>
            <dt className="text-lilac-50/50">Thumbnail</dt>
            <dd className="font-semibold text-lilac-50">
              {uploaded.has_thumbnail ? 'generated' : 'pending'}
            </dd>
          </dl>
        </div>
      )}
    </div>
  )
}
