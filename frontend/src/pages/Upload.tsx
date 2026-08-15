import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { formatBytes } from '../api/validation'
import { createPost, publishNow } from '../api/schedule'
import {
  cancel,
  getSnapshot,
  isBusy,
  reset,
  startUpload,
  subscribe,
} from '../api/uploadStore'

const USER_ID = 1

export default function Upload() {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [caption, setCaption] = useState('')

  // Subscribes to the module-level store, so an upload started here keeps
  // running - and keeps reporting progress - across navigation.
  const upload = useSyncExternalStore(subscribe, getSnapshot)
  const busy = isBusy(upload)

  const lastCompleted = useRef<number | null>(null)
  useEffect(() => {
    if (upload.completedAt && upload.completedAt !== lastCompleted.current) {
      lastCompleted.current = upload.completedAt
      queryClient.invalidateQueries({ queryKey: ['reels', USER_ID] })
    }
  }, [upload.completedAt, queryClient])

  // Post immediately: create the draft, then publish it in one action.
  const postNow = useMutation({
    mutationFn: async () => {
      if (!upload.uploaded) throw new Error('Nothing uploaded yet')
      const created = await createPost({
        userId: USER_ID,
        videoPath: upload.uploaded.path,
        caption: caption.trim() || undefined,
        platform: 'linkedin',
      })
      if (!created?.id) throw new Error('Could not determine the new post id')
      return publishNow(created.id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts', USER_ID] })
      queryClient.invalidateQueries({ queryKey: ['queue', USER_ID] })
    },
  })

  const handleFile = useCallback((file: File) => {
    void startUpload(file, USER_ID)
  }, [])

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

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
          if (file) handleFile(file)
          e.target.value = ''
        }}
      />

      {upload.phase === 'checking' && (
        <p className="mt-4 text-sm text-slate-600">Checking file&hellip;</p>
      )}

      {upload.phase === 'uploading' && (
        <div className="mt-6">
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>
              Uploading {upload.fileName ? `${upload.fileName} ` : ''}&hellip; {upload.progress}%
            </span>
            <button
              type="button"
              onClick={cancel}
              className="text-slate-500 underline hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-indigo-600 transition-all"
              style={{ width: `${upload.progress}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {upload.progress === 100
              ? 'Transfer complete — server is validating and generating a thumbnail…'
              : 'You can move to another page; this upload will keep running.'}
          </p>
        </div>
      )}

      {upload.phase === 'error' && upload.error && (
        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Upload failed</p>
          <p className="mt-1 text-sm text-red-700">{upload.error}</p>
          <button
            type="button"
            onClick={reset}
            className="mt-3 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          >
            Try again
          </button>
        </div>
      )}

      {upload.phase === 'done' && upload.uploaded && (
        <>
          <div className="mt-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-medium text-emerald-800">Uploaded</p>
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-emerald-900">
              <dt className="text-emerald-700">File</dt>
              <dd className="truncate">{upload.uploaded.filename}</dd>
              <dt className="text-emerald-700">Duration</dt>
              <dd>
                {upload.uploaded.duration_seconds != null
                  ? `${upload.uploaded.duration_seconds.toFixed(1)}s`
                  : 'unknown'}
              </dd>
              <dt className="text-emerald-700">Size</dt>
              <dd>{formatBytes(upload.uploaded.size_bytes)}</dd>
              <dt className="text-emerald-700">Thumbnail</dt>
              <dd>{upload.uploaded.has_thumbnail ? 'generated' : 'pending'}</dd>
            </dl>
          </div>

          <div className="mt-6 rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">Post now</h2>
            <p className="mt-1 text-xs text-slate-500">
              Publishes to LinkedIn immediately. To post later, use the Schedule page.
            </p>

            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={3}
              placeholder="Caption for the post"
              className="mt-3 w-full rounded-md border border-slate-300 p-2 text-sm"
            />

            {postNow.isSuccess ? (
              <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3">
                <p className="text-sm font-medium text-emerald-800">Published to LinkedIn</p>
                <a
                  href={postNow.data.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block break-all text-sm text-emerald-700 underline"
                >
                  {postNow.data.url}
                </a>
              </div>
            ) : (
              <>
                <button
                  type="button"
                  disabled={postNow.isPending}
                  onClick={() => postNow.mutate()}
                  className="mt-3 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
                >
                  {postNow.isPending ? 'Publishing…' : 'Post to LinkedIn now'}
                </button>
                {postNow.isPending && (
                  <p className="mt-2 text-xs text-slate-500">
                    LinkedIn is transcoding the video — this can take up to a minute.
                  </p>
                )}
                {postNow.isError && (
                  <p className="mt-2 text-sm text-red-700">
                    {(postNow.error as Error).message}
                  </p>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
