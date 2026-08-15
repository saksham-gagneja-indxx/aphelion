/**
 * Operations console API.
 *
 * Separate from admin.ts because the questions are different: admin is about
 * people, this is about the deployment it all runs on.
 */
import { apiFetch } from './auth'

export interface ConsoleOverview {
  runtime: {
    environment: string
    debug: boolean
    python: string
    platform: string
    pid: number
    timezone: string
  }
  database: {
    backend: string
    users: { total: number; pending_approval: number; guests: number }
    posts: { total: number; by_status: Record<string, number> }
    audit_events: number
  }
  scheduler: {
    enabled: boolean
    total_jobs?: number
    running?: boolean
    initialized?: boolean
    error?: string
  }
  storage: {
    reels: { bytes: number; files: number; path: string }
    uploads: { bytes: number; files: number; path: string }
    disk: { total: number; used: number; free: number } | null
  }
  features: Record<string, boolean>
}

export interface Orphan {
  path: string
  bytes: number
}

async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json()
    if (body?.error) return new Error(body.error)
  } catch {
    // ignore
  }
  return new Error(`Request failed (${res.status})`)
}

export async function getOverview(): Promise<ConsoleOverview> {
  const res = await apiFetch('/api/console/overview')
  if (!res.ok) {
    if (res.status === 403) throw new Error('Forbidden')
    throw await toError(res)
  }
  return res.json()
}

export async function listOrphans(): Promise<{
  orphans: Orphan[]
  count: number
  bytes: number
}> {
  const res = await apiFetch('/api/console/storage/orphans')
  if (!res.ok) throw await toError(res)
  return res.json()
}

export async function deleteOrphans(): Promise<{ deleted: number; bytes: number }> {
  const res = await apiFetch('/api/console/storage/orphans', { method: 'DELETE' })
  if (!res.ok) throw await toError(res)
  return res.json()
}

export async function purgeGuests(): Promise<{
  deleted_accounts: number
  deleted_posts: number
}> {
  const res = await apiFetch('/api/console/guests', { method: 'DELETE' })
  if (!res.ok) throw await toError(res)
  return res.json()
}
