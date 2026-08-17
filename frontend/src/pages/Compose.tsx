/**
 * The whole posting flow on one screen: pick a video, write a caption, choose
 * when.
 *
 * This replaces Upload and Schedule, which split the job across two pages and
 * made the common case — upload something and post it — a navigation exercise.
 * Both halves already existed; what is new is that neither is a destination.
 *
 * Two toggles, in the order the decisions are actually made:
 *   source  — upload a new file, or reuse one already there
 *   timing  — now, or at a chosen time
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { formatBytes } from '../api/validation'
import { apiFetch } from '../api/auth'
import {
  createPost,
  listReels,
  publishNow,
  schedulePost,
  thumbnailUrl,
} from '../api/schedule'
import { deleteReel } from '../api/queue'
import type { Reel } from '../api/types'
import type { ComposerDraft } from '../api/composer'
import { cancel, getSnapshot, isBusy, reset, startUpload, subscribe } from '../api/uploadStore'
import AssistantPanel from '../components/AssistantPanel'
import CaptionAssist from '../components/CaptionAssist'
import { useCurrentUser, useUserId } from '../current-user'
import { useUndo } from '../undo'
import {
  BANNER_DANGER,
  BANNER_QUIET,
  BTN_DANGER,
  BTN_OUTLINE,
  BTN_PRIMARY,
  EYEBROW,
  FIELD,
  H1,
  META,
  SUB,
} from '../ui'

type Source = 'upload' | 'existing'
type Timing = 'now' | 'later'

/** Segmented control. Square, hairline, violet fill on the active segment. */
function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
  label: string
}) {
  return (
    <div role="group" aria-label={label} className="flex w-full border border-line">
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            /* min-h-11 keeps this a 44px tap target on a phone. */
            className={`min-h-11 flex-1 px-4 py-2.5 text-[15px] transition ${
              active
                ? 'bg-mist-50 text-ink-950'
                : 'bg-ink-900 text-mist-500 hover:text-mist-50'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

/** Numbered section so the page reads as a sequence rather than a form. */
function Step({
  n,
  title,
  children,
  muted,
}: {
  n: number
  title: string
  children: React.ReactNode
  muted?: boolean
}) {
  return (
    <section className="surface p-5 transition sm:p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center border border-line bg-ink-800 text-[12px] text-violet-300">
          {n}
        </span>
        <h2 className={`${EYEBROW} !text-white`}>{title}</h2>
      </div>
      <div className={`mt-5 transition ${muted ? 'opacity-55 pointer-events-none grayscale' : ''}`}>
        {children}
      </div>
    </section>
  )
}

/** Progress bar during publish/schedule that animates to show activity */
function PublishProgress({ timing }: { timing: Timing }) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (timing === 'now') {
      // Publish flow: 5s upload (0-30%), 20s transcoding (30-90%), jump to 100%
      const uploadEnd = 5000

      const intervals = [
        // Upload phase: ramp 0→30% in 5s
        setInterval(() => {
          setProgress((p) => {
            if (p < 30) return Math.min(p + 6, 30)
            return p
          })
        }, 250),

        // Start transcoding after 5s: ramp 30→90% over next 20s
        setTimeout(
          () => {
            setInterval(() => {
              setProgress((p) => {
                if (p >= 30 && p < 90) return Math.min(p + 3, 90)
                return p
              })
            }, 250)
          },
          uploadEnd,
        ),
      ]

      return () => {
        if (typeof intervals[0] === 'number') clearInterval(intervals[0])
        if (typeof intervals[1] === 'number') clearTimeout(intervals[1])
      }
    } else {
      // Schedule flow: quick ramp to 100% (just creating a database record)
      const interval = setInterval(() => {
        setProgress((p) => Math.min(p + 20, 100))
      }, 100)
      return () => clearInterval(interval)
    }
  }, [timing])

  return (
    <>
      <div className="h-2 overflow-hidden rounded bg-ink-800">
        <div
          className="h-full animate-shimmer bg-[linear-gradient(90deg,#48008C,#8A05FF,#C29EFF)] bg-[length:260px_100%] transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className={`${META}`}>
        {progress < 50
          ? 'Uploading video…'
          : progress < 95
            ? 'LinkedIn is transcoding…'
            : 'Almost there…'}
      </p>
    </>
  )
}

/** Undo popup that appears after publish, allowing retraction within 15 seconds */
function UndoPublishPopup({ postId }: { postId: number | undefined }) {
  const [timeLeft, setTimeLeft] = useState(15)
  const [isUndoing, setIsUndoing] = useState(false)
  const [undoResult, setUndoResult] = useState<'success' | 'error' | null>(null)

  useEffect(() => {
    const interval = setInterval(() => {
      setTimeLeft((t) => t - 1)
    }, 1000)

    if (timeLeft <= 0) {
      clearInterval(interval)
    }

    return () => clearInterval(interval)
  }, [timeLeft])

  if (timeLeft <= 0) {
    return null
  }

  const handleUndo = async () => {
    if (!postId) return
    setIsUndoing(true)
    try {
      const res = await apiFetch(`/api/posts/${postId}/published`, {
        method: 'DELETE',
      })
      if (res.ok) {
        setUndoResult('success')
        setTimeout(() => setTimeLeft(0), 1500)
      } else {
        setUndoResult('error')
      }
    } catch (error) {
      setUndoResult('error')
    } finally {
      setIsUndoing(false)
    }
  }

  return (
    <div className="mt-4 border border-line border-l-2 border-l-orange-500 bg-ink-900 px-4 py-3.5">
      {undoResult === 'success' ? (
        <p className="text-[15px] text-mist-50">✓ Post removed from LinkedIn</p>
      ) : undoResult === 'error' ? (
        <p className="text-[15px] text-danger-soft">Could not retract post. Try from the queue.</p>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3">
            <p className="text-[15px] text-mist-200">
              Undo? You have{' '}
              <span className="font-semibold text-mist-50">{timeLeft}s</span>
            </p>
            <button
              type="button"
              onClick={handleUndo}
              disabled={isUndoing}
              className="shrink-0 rounded bg-orange-500/20 px-3 py-1.5 text-[14px] text-orange-300 transition hover:bg-orange-500/30 disabled:opacity-50"
            >
              {isUndoing ? 'Retracting…' : 'Retract'}
            </button>
          </div>
          <div className="mt-2 h-1 overflow-hidden bg-ink-800">
            <div
              className="h-full bg-orange-500 transition-all"
              style={{ width: `${(timeLeft / 15) * 100}%` }}
            />
          </div>
        </>
      )}
    </div>
  )
}

export default function Compose() {
  const USER_ID = useUserId()
  const user = useCurrentUser()
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)

  const [source, setSource] = useState<Source>('upload')
  const [timing, setTiming] = useState<Timing>('now')
  const [dragging, setDragging] = useState(false)
  const [caption, setCaption] = useState('')
  const [captionFromAssist, setCaptionFromAssist] = useState(false)
  const [picked, setPicked] = useState<Reel | null>(null)
  const [when, setWhen] = useState('')
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [lastPublishedPostId, setLastPublishedPostId] = useState<number | null>(null)

  const upload = useSyncExternalStore(subscribe, getSnapshot)
  const busy = isBusy(upload)

  // Always on, not gated to the "existing" tab: the assistant needs the full
  // list to resolve whatever reel_filename it picks into a real Reel, even
  // while the visible tab is "Upload new".
  const reelsQuery = useQuery({
    queryKey: ['reels', USER_ID],
    queryFn: () => listReels(USER_ID),
  })

  const lastCompleted = useRef<number | null>(null)
  useEffect(() => {
    if (upload.completedAt && upload.completedAt !== lastCompleted.current) {
      lastCompleted.current = upload.completedAt
      void queryClient.invalidateQueries({ queryKey: ['reels', USER_ID] })
    }
  }, [upload.completedAt, queryClient, USER_ID])

  const { pendingKeys, scheduleDelete } = useUndo()
  const reels = (reelsQuery.data?.reels ?? []).filter(
    (r) => !pendingKeys.has(`reel:${r.filename}`),
  )

  // Whichever source is active decides what gets posted, so the rest of the
  // page can ask one question instead of branching on `source` everywhere.
  const chosen = useMemo(() => {
    if (source === 'upload') {
      return upload.phase === 'done' && upload.uploaded
        ? {
            path: upload.uploaded.path,
            filename: upload.uploaded.filename,
            duration: upload.uploaded.duration_seconds,
          }
        : null
    }
    return picked
      ? { path: picked.path, filename: picked.filename, duration: picked.duration_seconds }
      : null
  }, [source, upload, picked])

  const submit = useMutation({
    mutationFn: async () => {
      if (!chosen) throw new Error('Choose a video first')
      if (timing === 'later' && !when) throw new Error('Pick a time first')

      const created = await createPost({
        userId: USER_ID,
        videoPath: chosen.path,
        caption: caption.trim() || undefined,
        aiGeneratedCaption: captionFromAssist,
        platform: 'linkedin',
      })
      if (!created?.id) throw new Error('Could not determine the new post id')

      const result = timing === 'now'
        ? { kind: 'published' as const, result: await publishNow(created.id), postId: created.id }
        : { kind: 'scheduled' as const, result: await schedulePost(created.id, when), postId: created.id }

      if (result.kind === 'published') {
        setLastPublishedPostId(result.postId)
      }

      return result
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['posts', USER_ID] })
      void queryClient.invalidateQueries({ queryKey: ['scheduledJobs', USER_ID] })
      setCaption('')
      setCaptionFromAssist(false)
      setPicked(null)
      setWhen('')
      if (source === 'upload') reset()
    },
  })

  const handleDeleteReel = (reel: Reel) => {
    setPicked((c) => (c?.path === reel.path ? null : c))
    scheduleDelete({
      key: `reel:${reel.filename}`,
      label: `Deleted ${reel.filename}`,
      commit: (init) => deleteReel(USER_ID, reel.filename, init),
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ['reels', USER_ID] })
      },
    })
  }

  const handleFile = useCallback(
    (file: File) => {
      void startUpload(file, USER_ID)
    },
    [USER_ID],
  )

  /**
   * Wire an assistant turn's draft into this screen's own state.
   *
   * Called after every turn, not just when the conversation ends, so the
   * boxes below fill in live while the panel is still open — the point of
   * folding the assistant into this page rather than keeping it a
   * destination with its own draft summary to reconcile back in.
   */
  const applyAssistantDraft = useCallback(
    (draft: ComposerDraft) => {
      if (draft.reel_filename) {
        const match = (reelsQuery.data?.reels ?? []).find(
          (r) => r.filename === draft.reel_filename,
        )
        if (match) {
          setSource('existing')
          setPicked(match)
        }
      }
      if (draft.caption) {
        setCaption(draft.caption)
        setCaptionFromAssist(true)
      }
      if (draft.when) {
        if (draft.when === 'now') {
          setTiming('now')
        } else {
          // Same YYYY-MM-DDTHH:MM shape the datetime-local input already uses.
          setTiming('later')
          setWhen(draft.when)
        }
      }
    },
    [reelsQuery.data],
  )

  const canSubmit = !!chosen && (timing === 'now' || !!when) && !submit.isPending

  return (
    <div className="mx-auto max-w-2xl animate-rise-in">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className={H1}>New post</h1>
          <p className={SUB}>Pick a video, write a caption, choose when it goes out.</p>
        </div>
        {/* Not sure what to post at all, rather than "help with this one
            caption" — that is CaptionAssist's job, scoped to Step 2. This
            one can also pick the video, so it lives up here instead. */}
        <button
          type="button"
          onClick={() => setAssistantOpen(true)}
          className={`${BTN_OUTLINE} mt-1 shrink-0`}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <path d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
          </svg>
          Not sure what to post?
        </button>
      </div>

      {user.is_guest ? (
        <div className={`${BANNER_QUIET} mt-6`}>
          <p className="text-[15px] text-mist-200">
            Guest account: upload, caption and scheduling all work. Publishing needs
            LinkedIn, because it posts to a real profile.
          </p>
        </div>
      ) : (
        !user.linkedin_connected && (
          <div className={`${BANNER_QUIET} mt-6`}>
            <p className="text-[15px] text-mist-200">
              LinkedIn is not connected, so nothing can be published yet.{' '}
              <Link to="/setup" className="text-violet-300 underline underline-offset-2">
                Finish setup
              </Link>
            </p>
          </div>
        )
      )}

      <div className="mt-8 space-y-3">
        <Step n={1} title="Video">
          <Segmented
            label="Video source"
            value={source}
            onChange={setSource}
            options={[
              { value: 'upload', label: 'Upload new' },
              { value: 'existing', label: 'Choose existing' },
            ]}
          />

          {source === 'upload' ? (
            <div className="mt-5">
              {upload.phase !== 'done' && (
                <div
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragging(true)
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault()
                    setDragging(false)
                    const file = e.dataTransfer.files?.[0]
                    if (file) handleFile(file)
                  }}
                  onClick={() => !busy && inputRef.current?.click()}
                  className={[
                    'flex h-[200px] cursor-pointer flex-col items-center justify-center border border-dashed transition',
                    dragging
                      ? 'border-violet-500 bg-violet-500/[0.06]'
                      : 'border-line bg-ink-900 hover:border-violet-500 hover:bg-violet-500/[0.04]',
                    busy ? 'pointer-events-none opacity-50' : '',
                  ].join(' ')}
                >
                  <svg className="h-8 w-8 text-violet-500" fill="none" stroke="currentColor"
                    strokeWidth={1.2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round"
                      d="M12 16.5V9m0 0L8.25 12.75M12 9l3.75 3.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                  <p className="mt-4 text-[17px] text-mist-50">
                    Drop a video, or <span className="text-violet-300">browse</span>
                  </p>
                  <p className={`${META} mt-2 px-4 text-center`}>
                    MP4, MOV, AVI, MKV or WEBM &middot; up to 90s &middot; max 500&nbsp;MB
                  </p>
                </div>
              )}

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
                <p className="mt-4 text-[16px] text-mist-500">Checking file&hellip;</p>
              )}

              {upload.phase === 'uploading' && (
                <div className={`${BANNER_QUIET} mt-4`}>
                  <div className="flex items-center justify-between text-[15px] text-mist-200">
                    <span className="truncate">
                      Uploading {upload.fileName ?? ''} &hellip; {upload.progress}%
                    </span>
                    <button type="button" onClick={cancel}
                      className="shrink-0 pl-3 text-mist-500 underline transition hover:text-mist-50">
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
                      ? 'Transfer complete — validating and generating a thumbnail…'
                      : 'You can move to another page; this upload keeps running.'}
                  </p>
                </div>
              )}

              {upload.phase === 'error' && upload.error && (
                <div className={`${BANNER_DANGER} mt-4`}>
                  <p className="text-[16px] text-danger-soft">Upload failed</p>
                  <p className="mt-1 text-[15px] text-danger-soft/75">{upload.error}</p>
                  <button type="button" onClick={reset} className={`${BTN_DANGER} mt-4`}>
                    Try again
                  </button>
                </div>
              )}

              {upload.phase === 'done' && upload.uploaded && (
                <div className="border border-line border-l-2 border-l-violet-500 bg-ink-900 px-4 py-3.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="min-w-0 truncate text-[16px] text-mist-50">
                      {upload.uploaded.filename}
                    </p>
                    <button type="button" onClick={reset}
                      className="shrink-0 text-[14px] text-mist-500 underline transition hover:text-mist-50">
                      Replace
                    </button>
                  </div>
                  <p className={`${META} mt-1`}>
                    {upload.uploaded.duration_seconds != null
                      ? `${upload.uploaded.duration_seconds.toFixed(1)}s`
                      : 'unknown length'}{' '}
                    &middot; {formatBytes(upload.uploaded.size_bytes)}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="mt-5">
              {reelsQuery.isPending && (
                <p className="text-[16px] text-mist-500">Loading reels&hellip;</p>
              )}
              {reelsQuery.isError && (
                <p className="text-[15px] text-danger-soft">
                  Could not load reels: {(reelsQuery.error as Error).message}
                </p>
              )}
              {reelsQuery.isSuccess && reels.length === 0 && (
                <p className="text-[16px] text-mist-500">
                  Nothing uploaded yet — switch to “Upload new”.
                </p>
              )}
              {reels.length > 0 && (
                <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {reels.map((reel) => {
                    const isPicked = picked?.path === reel.path
                    return (
                      <li key={reel.path} className="relative">
                        <button
                          type="button"
                          onClick={() => handleDeleteReel(reel)}
                          aria-label={`Delete ${reel.filename}`}
                          className="absolute right-2 top-2 z-10 border border-line bg-ink-950/80 p-1.5 text-mist-500 backdrop-blur transition hover:border-danger/50 hover:text-danger"
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth={1.5} strokeLinecap="round"
                            strokeLinejoin="round">
                            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          onClick={() => setPicked(isPicked ? null : reel)}
                          className={`w-full border text-left transition ${
                            isPicked
                              ? 'border-violet-500 bg-violet-500/[0.06]'
                              : 'border-line bg-ink-900 hover:border-mist-500'
                          }`}
                        >
                          <div className="flex h-[120px] w-full items-center justify-center overflow-hidden bg-ink-800">
                            {reel.has_thumbnail ? (
                              <img src={thumbnailUrl(USER_ID, reel.filename)} alt=""
                                className="h-full w-full object-cover" loading="lazy" />
                            ) : (
                              <svg className="h-5 w-5 text-mist-500" viewBox="0 0 24 24"
                                fill="none" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round"
                                  d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25z" />
                              </svg>
                            )}
                          </div>
                          <p className={`truncate px-3 py-2 text-[14px] ${
                            isPicked ? 'text-mist-50' : 'text-mist-200'
                          }`}>
                            {reel.filename}
                          </p>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )}
        </Step>

        <Step n={2} title="Caption" muted={false}>
          <textarea
            value={caption}
            onChange={(e) => {
              setCaption(e.target.value)
              setCaptionFromAssist(false)
            }}
            rows={4}
            placeholder="What is this about?"
            className={FIELD}
          />
          {(chosen || upload.uploaded) && (
            <CaptionAssist
              reelFilename={chosen?.filename ?? upload.uploaded?.filename ?? ''}
              durationSeconds={chosen?.duration ?? upload.uploaded?.duration_seconds ?? 0}
              onPick={(text) => {
                setCaption(text)
                setCaptionFromAssist(true)
              }}
            />
          )}
        </Step>

        <Step n={3} title="When" muted={!chosen}>
          <Segmented
            label="When to post"
            value={timing}
            onChange={setTiming}
            options={[
              { value: 'now', label: 'Post now' },
              { value: 'later', label: 'Schedule for later' },
            ]}
          />

          {timing === 'later' && (
            <div className="mt-4">
              <input
                type="datetime-local"
                value={when}
                onChange={(e) => setWhen(e.target.value)}
                className={FIELD}
              />
              <p className={`${META} mt-2`}>
                Interpreted in the account timezone configured on the backend.
              </p>
              <p className={`${META} mt-1`}>
                Free-tier hosting may delay publishing by up to 15 minutes past the scheduled time.
              </p>
            </div>
          )}

          {submit.isSuccess ? (
            <>
              <div className="mt-5 border border-line border-l-2 border-l-violet-500 bg-ink-900 px-4 py-3.5">
                {submit.data.kind === 'published' ? (
                  <>
                    <p className="text-[16px] text-mist-50">Published to LinkedIn</p>
                    <a href={submit.data.result.url} target="_blank" rel="noreferrer"
                      className="mt-1 inline-block break-all text-[15px] text-violet-300 underline">
                      {submit.data.result.url}
                    </a>
                  </>
                ) : (
                  <>
                    <p className="text-[16px] text-mist-50">Scheduled</p>
                    <p className={`${META} mt-1`}>
                      Track it in the{' '}
                      <Link to="/queue" className="text-violet-300 underline underline-offset-2">
                        queue
                      </Link>
                      .
                    </p>
                  </>
                )}
              </div>
              {submit.data.kind === 'published' && (
                <UndoPublishPopup postId={lastPublishedPostId ?? undefined} />
              )}
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={!canSubmit}
                onClick={() => submit.mutate()}
                className={`${BTN_PRIMARY} mt-5 w-full sm:w-auto`}
              >
                {submit.isPending
                  ? timing === 'now'
                    ? 'Publishing…'
                    : 'Scheduling…'
                  : timing === 'now'
                    ? 'Post to LinkedIn now'
                    : 'Schedule post'}
              </button>
              {submit.isPending && (
                <div className="mt-4 space-y-2">
                  <PublishProgress timing={timing} />
                </div>
              )}
              {submit.isError && (
                <p className="mt-3 text-[15px] text-danger-soft">
                  {(submit.error as Error).message}
                </p>
              )}
            </>
          )}
        </Step>
      </div>

      <AssistantPanel
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        onApplyDraft={applyAssistantDraft}
      />
    </div>
  )
}
