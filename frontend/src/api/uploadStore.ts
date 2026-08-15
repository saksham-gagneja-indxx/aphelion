/**
 * Upload state held OUTSIDE React.
 *
 * The upload used to live in Upload.tsx's component state. Navigating to
 * another page unmounted the component, and although the XHR kept running, all
 * progress and the eventual result were lost - so it looked like the upload
 * had stopped. Coming back showed an idle dropzone mid-transfer.
 *
 * Keeping the state in a module-level store means it survives unmounting:
 * navigate away, come back, and the progress bar is still where it should be.
 * Components subscribe via useSyncExternalStore.
 *
 * A plain store rather than React context because a context provider would
 * have to be mounted in App.tsx, which another session owns - and because this
 * state genuinely is not tied to any component's lifetime.
 */

import { uploadReel } from './client'
import type { Reel } from './types'

export type UploadPhase = 'idle' | 'checking' | 'uploading' | 'done' | 'error'

export interface UploadState {
  phase: UploadPhase
  progress: number
  error: string | null
  uploaded: Reel | null
  fileName: string | null
  /** Bumped on each successful upload so subscribers can refetch exactly once. */
  completedAt: number | null
}

const initialState: UploadState = {
  phase: 'idle',
  progress: 0,
  error: null,
  uploaded: null,
  fileName: null,
  completedAt: null,
}

let state: UploadState = initialState
let controller: AbortController | null = null

const listeners = new Set<() => void>()

function emit(patch: Partial<UploadState>) {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Identity-stable while nothing changes, which useSyncExternalStore requires. */
export function getSnapshot(): UploadState {
  return state
}

export function isBusy(s: UploadState = state): boolean {
  return s.phase === 'checking' || s.phase === 'uploading'
}

export function reset() {
  controller = null
  emit(initialState)
}

export function cancel() {
  controller?.abort()
  controller = null
  emit({ phase: 'idle', progress: 0, error: null, fileName: null })
}

/**
 * Validate then upload. Safe to call from a component that later unmounts -
 * nothing here touches React state.
 */
export async function startUpload(file: File, userId: number): Promise<void> {
  if (isBusy()) return

  const { preflight } = await import('./validation')

  emit({
    phase: 'checking',
    progress: 0,
    error: null,
    uploaded: null,
    fileName: file.name,
  })

  const problem = await preflight(file)
  if (problem) {
    emit({ phase: 'error', error: problem })
    return
  }

  controller = new AbortController()
  emit({ phase: 'uploading' })

  try {
    const res = await uploadReel({
      file,
      userId,
      onProgress: (progress) => emit({ progress }),
      signal: controller.signal,
    })
    emit({
      phase: 'done',
      uploaded: res.reel,
      progress: 100,
      completedAt: Date.now(),
    })
  } catch (err) {
    // A user-initiated cancel is not an error worth shouting about.
    if (err instanceof Error && err.name === 'AbortError') {
      emit({ phase: 'idle', progress: 0, fileName: null })
      return
    }
    emit({
      phase: 'error',
      error: err instanceof Error ? err.message : 'Upload failed',
    })
  } finally {
    controller = null
  }
}
