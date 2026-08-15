/**
 * Caption assist API.
 *
 * The server writes captions from the brief the operator types, not from the
 * video — see backend/core/captions.py for why. The reel filename is optional
 * and only supplies a thumbnail as weak visual context.
 */
import { apiFetch } from './auth'

export interface CaptionOption {
  angle: string
  text: string
}

export interface CaptionStatus {
  available: boolean
  reason: string | null
}

async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json()
    if (body?.error) return new Error(body.error)
  } catch {
    // non-JSON body
  }
  return new Error(`Request failed (${res.status})`)
}

/** Whether the server can generate captions at all — key present, flag on. */
export async function getCaptionStatus(): Promise<CaptionStatus> {
  const res = await apiFetch('/api/captions/status')
  if (!res.ok) throw await toError(res)
  return res.json()
}

export async function suggestCaptions(input: {
  brief: string
  reelFilename?: string
  durationSeconds?: number | null
}): Promise<{ captions: CaptionOption[]; used_thumbnail: boolean }> {
  const res = await apiFetch('/api/captions/suggest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      brief: input.brief,
      reel_filename: input.reelFilename,
      duration_seconds: input.durationSeconds ?? undefined,
    }),
  })
  if (!res.ok) throw await toError(res)
  return res.json()
}
