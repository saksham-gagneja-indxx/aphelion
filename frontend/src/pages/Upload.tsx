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
import CaptionAssist from '../components/CaptionAssist'
import {
  BANNER_DANGER,
  BANNER_QUIET,
  BTN_DANGER,
  BTN_PRIMARY,
  FIELD,
  H1,
  H2,
  META,
  SUB,
} from '../ui'

const USER_ID = 1

export default function Upload() {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [caption, setCaption] = useState('')
  // See Schedule.tsx: records a drafted caption, cleared the moment the
  // operator edits it themselves.
  const [captionFromAssist, setCaptionFromAssist] = useState(false)

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
        aiGeneratedCaption: captionFromAssist,
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
          if (file) handleFile(file)
          e.target.value = ''
        }}
      />

      {upload.phase === 'checking' && (
        <p className="mt-6 text-[16px] text-mist-500">Checking file&hellip;</p>
      )}

      {upload.phase === 'uploading' && (
        <div className={`${BANNER_QUIET} mt-6`}>
          <div className="flex items-center justify-between text-[15px] text-mist-200">
            <span>
              Uploading {upload.fileName ? `${upload.fileName} ` : ''}&hellip; {upload.progress}%
            </span>
            <button
              type="button"
              onClick={cancel}
              className="text-mist-500 underline transition hover:text-mist-50"
            >
              Cancel
            </button>
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden bg-ink-800">
            <div
              className="h-full animate-shimmer bg-[linear-gradient(90deg,#48008C,#8A05FF,#C29EFF)] bg-[length:260px_100%] transition-all"
              style={{ width: `${upload.progress}%` }}
            />
          </div>
          <p className={`${META} mt-3`}>
            {upload.progress === 100
              ? 'Transfer complete — server is validating and generating a thumbnail…'
              : 'You can move to another page; this upload will keep running.'}
          </p>
        </div>
      )}

      {upload.phase === 'error' && upload.error && (
        <div className={`${BANNER_DANGER} mt-6`}>
          <p className="text-[16px] text-danger-soft">Upload failed</p>
          <p className="mt-1 text-[15px] text-danger-soft/75">{upload.error}</p>
          {/* Destructive is always outlined — nothing red is ever a fill. */}
          <button type="button" onClick={reset} className={`${BTN_DANGER} mt-4`}>
            Try again
          </button>
        </div>
      )}

      {upload.phase === 'done' && upload.uploaded && (
        <>
          <div className="mt-6 border border-line border-l-2 border-l-violet-500 bg-ink-900 px-5 py-4">
            <p className="text-[16px] text-mist-50">Uploaded</p>
            <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-8 gap-y-2 text-[15px]">
              <dt className="text-mist-500">File</dt>
              <dd className="truncate text-mist-50">{upload.uploaded.filename}</dd>
              <dt className="text-mist-500">Duration</dt>
              <dd className="text-mist-50">
                {upload.uploaded.duration_seconds != null
                  ? `${upload.uploaded.duration_seconds.toFixed(1)}s`
                  : 'unknown'}
              </dd>
              <dt className="text-mist-500">Size</dt>
              <dd className="text-mist-50">{formatBytes(upload.uploaded.size_bytes)}</dd>
              <dt className="text-mist-500">Thumbnail</dt>
              <dd className="text-mist-50">
                {upload.uploaded.has_thumbnail ? 'generated' : 'pending'}
              </dd>
            </dl>
          </div>

          <div className="surface mt-3 p-5">
            <h2 className={H2}>Post now</h2>
            <p className={`${META} mt-1`}>
              Publishes to LinkedIn immediately. To post later, use the Schedule page.
            </p>

            <textarea
              value={caption}
              onChange={(e) => {
                setCaption(e.target.value)
                setCaptionFromAssist(false)
              }}
              rows={3}
              placeholder="Caption for the post"
              className={`${FIELD} mt-4`}
            />

            <CaptionAssist
              reelFilename={upload.uploaded.filename}
              durationSeconds={upload.uploaded.duration_seconds}
              onPick={(text) => {
                setCaption(text)
                setCaptionFromAssist(true)
              }}
            />

            {postNow.isSuccess ? (
              <div className="mt-4 border border-line border-l-2 border-l-violet-500 bg-ink-900 px-4 py-3.5">
                <p className="text-[16px] text-mist-50">Published to LinkedIn</p>
                <a
                  href={postNow.data.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block break-all text-[15px] text-violet-300 underline"
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
                  className={`${BTN_PRIMARY} mt-4`}
                >
                  {postNow.isPending ? 'Publishing…' : 'Post to LinkedIn now'}
                </button>
                {postNow.isPending && (
                  <p className={`${META} mt-3`}>
                    LinkedIn is transcoding the video — this can take up to a minute.
                  </p>
                )}
                {postNow.isError && (
                  <p className="mt-3 text-[15px] text-danger-soft">
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
