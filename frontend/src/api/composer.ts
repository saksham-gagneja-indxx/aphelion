/**
 * Conversational composer API.
 *
 * Stateless by design: the whole transcript and the current draft go up with
 * every turn, and the server holds nothing between them. That matches how the
 * rest of this app works — a signed session token and no server-side session
 * store — and avoids a conversations table whose retention nobody has decided.
 *
 * Note what is missing: there is no publish call here. The composer produces a
 * draft; publishing it goes through the ordinary post/schedule endpoints,
 * driven by a human pressing a button. See backend/core/composer.py.
 */
import { apiFetch } from './auth'

export interface ComposerMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ComposerDraft {
  reel_filename: string | null
  caption: string | null
  angle: string | null
  /** 'now', or a naive local datetime — the shape the schedule endpoint takes. */
  when: string | null
}

export interface ComposerTurn {
  reply: string
  draft: ComposerDraft
  ready: boolean
  /** One line per tool the model ran, so the UI can show its working. */
  actions: string[]
}

export const emptyDraft = (): ComposerDraft => ({
  reel_filename: null,
  caption: null,
  angle: null,
  when: null,
})

async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json()
    if (body?.error) return new Error(body.error)
  } catch {
    /* non-JSON body */
  }
  return new Error(`Request failed (${res.status})`)
}

export async function getComposerStatus(): Promise<{
  available: boolean
  reason: string | null
}> {
  const res = await apiFetch('/api/composer/status')
  if (!res.ok) throw await toError(res)
  return res.json()
}

export async function composerTurn(input: {
  messages: ComposerMessage[]
  draft: ComposerDraft
}): Promise<ComposerTurn> {
  const res = await apiFetch('/api/composer/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw await toError(res)
  return res.json()
}
