/**
 * Assistant — say what you want, get a post.
 *
 * The lazy path. Drop a line like "post the OAuth reel tomorrow at 9" and
 * Claude picks the reel, writes the caption and proposes the time. If
 * something is missing it asks for one thing, not a form.
 *
 * The draft it builds sits alongside the conversation and is always visible,
 * because the interesting output of a chat with an assistant is not the chat.
 * When all three fields are filled the buttons light up — and pressing one is
 * the human's job. Claude has no publish tool and the server has no route that
 * would let it acquire one; see backend/core/composer.py for why that boundary
 * is where it is rather than a step that could be automated away.
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  composerTurn,
  emptyDraft,
  getComposerStatus,
  type ComposerDraft,
  type ComposerMessage,
} from '../api/composer'
import { createPost, listReels, publishNow, schedulePost } from '../api/schedule'
import { useUserId } from '../current-user'
import {
  BANNER_DANGER,
  BTN_OUTLINE,
  BTN_PRIMARY,
  BTN_QUIET,
  EYEBROW,
  FIELD,
  H1,
  META,
  SUB,
} from '../ui'

const OPENERS = [
  'Post my newest reel tomorrow at 9am',
  'What should I post this week?',
  'Write a caption for the OAuth reel and schedule it Friday morning',
]

function formatWhen(when: string | null): string {
  if (!when) return 'not set'
  if (when === 'now') return 'immediately'
  const d = new Date(when)
  if (Number.isNaN(d.getTime())) return when
  return d.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** The draft as it stands. Three rows, filled or not. */
function DraftPanel({
  draft,
  ready,
  busy,
  onPublish,
  error,
}: {
  draft: ComposerDraft
  ready: boolean
  busy: boolean
  onPublish: () => void
  error: string | null
}) {
  const rows: { label: string; value: string | null }[] = [
    { label: 'Reel', value: draft.reel_filename },
    { label: 'Caption', value: draft.caption },
    { label: 'When', value: draft.when ? formatWhen(draft.when) : null },
  ]

  return (
    <aside className="surface p-5 lg:sticky lg:top-24">
      <h2 className={EYEBROW}>Draft</h2>

      <dl className="mt-4 flex flex-col gap-4">
        {rows.map((row) => (
          <div key={row.label}>
            <dt className={META}>{row.label}</dt>
            <dd
              className={`mt-1 text-[15px] break-words ${
                row.value ? 'text-mist-50' : 'text-mist-500 italic'
              }`}
            >
              {row.value ?? 'not set'}
            </dd>
          </div>
        ))}
      </dl>

      {error && (
        <div className={`${BANNER_DANGER} mt-4`}>
          <p className="text-[15px] text-danger-soft">{error}</p>
        </div>
      )}

      <button
        type="button"
        disabled={!ready || busy}
        onClick={onPublish}
        className={`${BTN_PRIMARY} mt-5 w-full`}
      >
        {busy
          ? 'Working…'
          : draft.when === 'now'
            ? 'Post now'
            : draft.when
              ? 'Schedule it'
              : 'Post'}
      </button>

      {/* Said plainly rather than implied. The person should know the
          assistant cannot act on its own. */}
      <p className={`${META} mt-3`}>
        Nothing is published until you press this. The assistant fills the
        draft; it cannot post on its own.
      </p>
    </aside>
  )
}

export default function Assistant() {
  const USER_ID = useUserId()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [messages, setMessages] = useState<ComposerMessage[]>([])
  const [draft, setDraft] = useState<ComposerDraft>(emptyDraft())
  const [ready, setReady] = useState(false)
  const [input, setInput] = useState('')
  const [publishError, setPublishError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const status = useQuery({
    queryKey: ['composerStatus'],
    queryFn: getComposerStatus,
    staleTime: 5 * 60_000,
    retry: false,
  })

  const reels = useQuery({
    queryKey: ['reels', USER_ID],
    queryFn: () => listReels(USER_ID),
  })

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length])

  const turn = useMutation({
    mutationFn: (next: ComposerMessage[]) => composerTurn({ messages: next, draft }),
    onSuccess: (res) => {
      setDraft(res.draft)
      setReady(res.ready)
      if (res.reply) {
        setMessages((m) => [...m, { role: 'assistant', content: res.reply }])
      }
    },
  })

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || turn.isPending) return
    const next: ComposerMessage[] = [...messages, { role: 'user', content: trimmed }]
    setMessages(next)
    setInput('')
    turn.mutate(next)
  }

  /**
   * Turn the draft into a real post.
   *
   * Deliberately here in the browser rather than on the composer endpoint:
   * this is the human's action, and it goes through exactly the same
   * create/schedule/publish calls the manual screen uses. One code path to
   * publishing, and it always starts with a click.
   */
  const publish = useMutation({
    mutationFn: async () => {
      if (!draft.reel_filename || !draft.caption || !draft.when) {
        throw new Error('The draft is not finished yet.')
      }
      const reel = (reels.data?.reels ?? []).find(
        (r) => r.filename === draft.reel_filename,
      )
      if (!reel) throw new Error(`Reel "${draft.reel_filename}" is no longer there.`)

      const post = await createPost({
        userId: USER_ID,
        videoPath: reel.path,
        caption: draft.caption,
        aiGeneratedCaption: true,
        platform: 'linkedin',
      })
      if (draft.when === 'now') return publishNow(post.id)
      return schedulePost(post.id, draft.when)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts', USER_ID] })
      queryClient.invalidateQueries({ queryKey: ['scheduledJobs', USER_ID] })
      navigate('/queue')
    },
    onError: (e: Error) => setPublishError(e.message),
  })

  if (status.isSuccess && !status.data.available) {
    return (
      <div className="mx-auto max-w-2xl animate-rise-in">
        <h1 className={H1}>Assistant</h1>
        <p className={SUB}>Describe the post you want and it gets drafted for you.</p>
        <div className={`${BANNER_DANGER} mt-8`}>
          <p className="text-[15px] text-danger-soft">
            {status.data.reason ?? 'The assistant is not configured.'}
          </p>
        </div>
      </div>
    )
  }

  const started = messages.length > 0

  return (
    <div className="mx-auto max-w-[1100px] animate-rise-in">
      <h1 className={H1}>Assistant</h1>
      <p className={SUB}>
        Say what you want posted. It picks the reel, writes the caption and
        proposes a time.
      </p>

      {/* One column on a phone with the draft on top, so the thing being built
          is visible without scrolling past the whole conversation. Two columns
          from lg, where there is room for both at once. */}
      <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="order-2 lg:order-1">
          <div className="surface flex min-h-[360px] flex-col p-5">
            <div className="flex-1 space-y-4">
              {!started && (
                <div>
                  <p className="text-[16px] text-mist-200">
                    Tell me what to post — or pick one of these.
                  </p>
                  <div className="mt-4 flex flex-col items-start gap-2">
                    {OPENERS.map((o) => (
                      <button
                        key={o}
                        type="button"
                        onClick={() => send(o)}
                        className={`${BTN_QUIET} text-left`}
                      >
                        {o}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) => (
                <div
                  key={i}
                  className={
                    m.role === 'user'
                      ? 'ml-auto max-w-[85%] border border-violet-500/45 bg-violet-500/[0.1] px-4 py-3'
                      : 'max-w-[90%] border border-line bg-ink-800 px-4 py-3'
                  }
                >
                  <p className="text-[15px] leading-[1.6] whitespace-pre-wrap text-mist-100">
                    {m.content}
                  </p>
                </div>
              ))}

              {turn.isPending && (
                <p className={`${META} animate-pulse`}>Thinking…</p>
              )}

              {turn.isError && (
                <div className={BANNER_DANGER}>
                  <p className="text-[15px] text-danger-soft">
                    {(turn.error as Error).message}
                  </p>
                </div>
              )}
              <div ref={endRef} />
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                send(input)
              }}
              className="mt-5 flex flex-col gap-3 sm:flex-row"
            >
              <label htmlFor="assistant-input" className="sr-only">
                Message the assistant
              </label>
              <input
                id="assistant-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Post the OAuth reel tomorrow at 9am"
                className={`${FIELD} flex-1`}
                autoComplete="off"
              />
              <button
                type="submit"
                disabled={!input.trim() || turn.isPending}
                className={`${BTN_OUTLINE} shrink-0`}
              >
                Send
              </button>
            </form>
          </div>
        </div>

        <div className="order-1 lg:order-2">
          <DraftPanel
            draft={draft}
            ready={ready}
            busy={publish.isPending}
            error={publishError}
            onPublish={() => {
              setPublishError(null)
              publish.mutate()
            }}
          />
        </div>
      </div>
    </div>
  )
}
