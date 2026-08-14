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
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">Upload a reel</h1>
      <p className="mt-1 text-sm text-slate-500">
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
          'mt-6 flex h-56 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed transition',
          dragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 bg-white hover:border-slate-400',
          busy ? 'pointer-events-none opacity-60' : '',
        ].join(' ')}
      >
        <svg className="h-10 w-10 text-slate-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9m0 0L8.25 12.75M12 9l3.75 3.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        <p className="mt-3 text-sm font-medium text-slate-700">
          Drop a video here, or <span className="text-indigo-600">browse</span>
        </p>
        <p className="mt-1 text-xs text-slate-400">Validated locally before upload starts</p>
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
        <p className="mt-4 text-sm text-slate-600">Checking file&hellip;</p>
      )}

      {phase === 'uploading' && (
        <div className="mt-6">
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>Uploading&hellip; {progress}%</span>
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="text-slate-500 underline hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-indigo-600 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          {progress === 100 && (
            <p className="mt-2 text-xs text-slate-500">
              Transfer complete &mdash; server is validating and generating a thumbnail&hellip;
            </p>
          )}
        </div>
      )}

      {phase === 'error' && error && (
        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Upload failed</p>
          <p className="mt-1 text-sm text-red-700">{error}</p>
          <button
            type="button"
            onClick={() => {
              setPhase('idle')
              setError(null)
            }}
            className="mt-3 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          >
            Try again
          </button>
        </div>
      )}

      {phase === 'done' && uploaded && (
        <div className="mt-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-medium text-emerald-800">Uploaded</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-emerald-900">
            <dt className="text-emerald-700">File</dt>
            <dd className="truncate">{uploaded.filename}</dd>
            <dt className="text-emerald-700">Duration</dt>
            <dd>
              {uploaded.duration_seconds != null
                ? `${uploaded.duration_seconds.toFixed(1)}s`
                : 'unknown'}
            </dd>
            <dt className="text-emerald-700">Size</dt>
            <dd>{formatBytes(uploaded.size_bytes)}</dd>
            <dt className="text-emerald-700">Thumbnail</dt>
            <dd>{uploaded.has_thumbnail ? 'generated' : 'pending'}</dd>
          </dl>
        </div>
      )}
    </div>
  )
}
