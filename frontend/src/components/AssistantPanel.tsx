/**
 * Assistant — say what you want, watch the post fill in behind you.
 *
 * A popover, not a page. It used to be its own route: a full context switch
 * away from the thing it was helping with. Now it floats over Compose and
 * writes straight into that screen's own state as each turn lands — the
 * video gets picked, the caption gets typed, the time gets set, all in the
 * same Step 1/2/3 boxes a manual post would use. There is no separate draft
 * summary to reconcile back into the form, because there is no second form.
 *
 * It still cannot publish. See backend/core/composer.py for why that
 * boundary exists and why it stays put here too.
 */
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  composerTurn,
  emptyDraft,
  getComposerStatus,
  type ComposerDraft,
  type ComposerMessage,
} from '../api/composer'
import { BANNER_DANGER, BTN_OUTLINE, BTN_QUIET, FIELD, META } from '../ui'

const OPENERS = [
  'Post my newest reel tomorrow at 9am',
  'What should I post this week?',
  'Write a caption for the OAuth reel and schedule it Friday morning',
]

export default function AssistantPanel({
  open,
  onClose,
  onApplyDraft,
}: {
  open: boolean
  onClose: () => void
  /** Called after every turn with whatever the model filled in so far. */
  onApplyDraft: (draft: ComposerDraft) => void
}) {
  const [messages, setMessages] = useState<ComposerMessage[]>([])
  const [draft, setDraft] = useState<ComposerDraft>(emptyDraft())
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  const status = useQuery({
    queryKey: ['composerStatus'],
    queryFn: getComposerStatus,
    staleTime: 5 * 60_000,
    retry: false,
    enabled: open,
  })

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length])

  // Escape closes it, same as any overlay.
  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const turn = useMutation({
    mutationFn: (next: ComposerMessage[]) => composerTurn({ messages: next, draft }),
    onSuccess: (res) => {
      setDraft(res.draft)
      onApplyDraft(res.draft)
      if (res.reply) {
        setMessages((m) => [...m, { role: 'assistant', content: res.reply }])
      }
      // The draft is done — the boxes behind this now show it, so the popup
      // has nothing left to do. A short delay rather than an instant vanish:
      // long enough to read "draft is ready" before it's gone.
      if (res.ready) {
        window.setTimeout(onClose, 1100)
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

  if (!open) return null

  const started = messages.length > 0

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-ink-950/70 px-4 py-10 backdrop-blur-sm sm:items-center"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Assistant"
        className="surface flex w-full max-w-[640px] flex-col p-5 sm:p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[20px] text-mist-50">Assistant</h2>
            <p className={`${META} mt-1`}>
              Say what you want posted — it fills in the video, caption and time
              behind this.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close assistant"
            className="shrink-0 border border-line bg-ink-900 p-2 text-mist-500 transition hover:text-mist-50"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        {status.isSuccess && !status.data.available ? (
          <div className={`${BANNER_DANGER} mt-5`}>
            <p className="text-[15px] text-danger-soft">
              {status.data.reason ?? 'The assistant is not configured.'}
            </p>
          </div>
        ) : (
          <>
            <div className="mt-5 flex max-h-[45vh] min-h-[140px] flex-col gap-3 overflow-y-auto">
              {!started && (
                <div>
                  <p className="text-[15px] text-mist-200">
                    Tell me what to post — or pick one of these.
                  </p>
                  <div className="mt-3 flex flex-col items-start gap-2">
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

              {turn.isPending && <p className={`${META} animate-pulse`}>Thinking…</p>}

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
              className="mt-4 flex flex-col gap-3 sm:flex-row"
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
                autoFocus
              />
              <button
                type="submit"
                disabled={!input.trim() || turn.isPending}
                className={`${BTN_OUTLINE} shrink-0`}
              >
                Send
              </button>
            </form>

            <p className={`${META} mt-3`}>
              It fills in the boxes behind this as it goes. Nothing publishes until
              you press the button down there yourself.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
