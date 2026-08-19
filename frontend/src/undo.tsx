/**
 * Deletions that can be taken back for 15 seconds.
 *
 * Nothing is sent to the server until the window expires. That is what makes
 * "undo" honest — there is no delete to reverse, because it never happened —
 * and it means a mis-tap on a phone costs nothing.
 *
 * The cost of deferring is that closing the tab mid-window would silently
 * abandon the request, and the item would reappear on next load having
 * apparently ignored the user. So pending deletions are flushed on pagehide
 * with keepalive, which the browser will finish after the document is gone.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'

export const UNDO_WINDOW_MS = 15_000

interface Pending {
  key: string
  label: string
  commit: (init?: RequestInit) => Promise<unknown>
  onSettled?: () => void
  expiresAt: number
}

interface UndoApi {
  /** Keys currently pending deletion — callers hide these from their lists. */
  pendingKeys: ReadonlySet<string>
  /** Begin the window. Re-deleting the same key restarts it. */
  scheduleDelete: (entry: {
    key: string
    label: string
    commit: (init?: RequestInit) => Promise<unknown>
    onSettled?: () => void
  }) => void
  undo: (key: string) => void
}

const UndoContext = createContext<UndoApi | null>(null)

export function useUndo(): UndoApi {
  const ctx = useContext(UndoContext)
  if (!ctx) throw new Error('useUndo must be used inside <UndoProvider>')
  return ctx
}

export function UndoProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<Pending[]>([])
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>())
  // Mirrors `pending` for the unload handler, which cannot read React state.
  const pendingRef = useRef<Pending[]>([])
  pendingRef.current = pending

  const clearTimer = useCallback((key: string) => {
    const timer = timers.current.get(key)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(key)
    }
  }, [])

  const commitNow = useCallback(
    (key: string) => {
      clearTimer(key)
      setPending((current) => {
        const entry = current.find((p) => p.key === key)
        if (entry) {
          void Promise.resolve(entry.commit()).finally(() => entry.onSettled?.())
        }
        return current.filter((p) => p.key !== key)
      })
    },
    [clearTimer],
  )

  const scheduleDelete = useCallback<UndoApi['scheduleDelete']>(
    (entry) => {
      clearTimer(entry.key)
      const next: Pending = { ...entry, expiresAt: Date.now() + UNDO_WINDOW_MS }
      setPending((current) => [...current.filter((p) => p.key !== entry.key), next])
      timers.current.set(
        entry.key,
        setTimeout(() => commitNow(entry.key), UNDO_WINDOW_MS),
      )
    },
    [clearTimer, commitNow],
  )

  const undo = useCallback(
    (key: string) => {
      clearTimer(key)
      setPending((current) => {
        const entry = current.find((p) => p.key === key)
        entry?.onSettled?.()
        return current.filter((p) => p.key !== key)
      })
    },
    [clearTimer],
  )

  // Leaving the page confirms the deletions rather than abandoning them: the
  // user asked for them and let the window run. keepalive lets the request
  // outlive the document.
  useEffect(() => {
    const flush = () => {
      for (const entry of pendingRef.current) {
        try {
          void entry.commit({ keepalive: true })
        } catch {
          // Nothing useful to do while the page is going away.
        }
      }
    }
    window.addEventListener('pagehide', flush)
    return () => window.removeEventListener('pagehide', flush)
  }, [])

  useEffect(() => {
    const map = timers.current
    return () => map.forEach(clearTimeout)
  }, [])

  const value = useMemo<UndoApi>(
    () => ({
      pendingKeys: new Set(pending.map((p) => p.key)),
      scheduleDelete,
      undo,
    }),
    [pending, scheduleDelete, undo],
  )

  return (
    <UndoContext.Provider value={value}>
      {children}
      <UndoToasts pending={pending} onUndo={undo} />
    </UndoContext.Provider>
  )
}

/** Countdown ring plus the remaining seconds. */
function Countdown({ expiresAt }: { expiresAt: number }) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(tick)
  }, [])

  const remaining = Math.max(0, expiresAt - now)
  const seconds = Math.ceil(remaining / 1000)
  const fraction = remaining / UNDO_WINDOW_MS
  const circumference = 2 * Math.PI * 9

  return (
    <span className="relative inline-flex h-6 w-6 shrink-0 items-center justify-center">
      <svg className="absolute inset-0 -rotate-90" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2"
          className="text-line" />
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2"
          className="text-violet-500"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
        />
      </svg>
      <span className="text-[11px] text-mist-500">{seconds}</span>
    </span>
  )
}

function UndoToasts({
  pending,
  onUndo,
}: {
  pending: Pending[]
  onUndo: (key: string) => void
}) {
  if (pending.length === 0) return null

  // Portaled straight to <body>: UndoProvider (and this toast) lives inside
  // <main className="relative z-10">, which opens its own stacking context.
  // A z-50 in here would only ever out-rank things inside that same <main> -
  // it can't reach above BottomNav (z-30), which is <main>'s *sibling* and
  // physically overlaps this toast's bottom-of-screen position, silently
  // eating clicks meant for Undo. Escaping to <body> compares z-50 against
  // BottomNav directly, where it correctly wins.
  return createPortal(
    <div
      // Above the fold on a phone, out of the way on a desktop. pb-safe-ish
      // inset so it clears a browser's bottom chrome.
      className="fixed inset-x-4 bottom-6 z-50 flex flex-col gap-2 sm:left-auto sm:right-6 sm:w-[380px]"
      role="status"
      aria-live="polite"
    >
      {pending.map((entry) => (
        <div
          key={entry.key}
          className="surface-raised flex items-center gap-3 px-4 py-3 shadow-lg"
        >
          <Countdown expiresAt={entry.expiresAt} />
          <span className="min-w-0 flex-1 truncate text-[15px] text-mist-200">
            {entry.label}
          </span>
          <button
            type="button"
            onClick={() => onUndo(entry.key)}
            className="shrink-0 border border-mist-50 px-3 py-1.5 text-[14px] text-mist-50 transition hover:bg-mist-50/10"
          >
            Undo
          </button>
        </div>
      ))}
    </div>,
    document.body,
  )
}
