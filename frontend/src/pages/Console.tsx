/**
 * Operations console — the state of the deployment, and a few levers.
 *
 * Deliberately a different page from Admin, on a different route. Admin
 * answers "who is using this and what may they do"; this answers "is the thing
 * actually running, and where is the disk going". Mixing them made the admin
 * page a dumping ground for anything vaguely privileged.
 *
 * Destructive actions here confirm before acting rather than using the undo
 * window the rest of the app uses: these are bulk and irreversible — purging
 * guests removes their posts too, and deleting orphans removes files — so a
 * quiet fifteen seconds is the wrong shape.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMe } from '../api/auth'
import {
  deleteOrphans,
  getOverview,
  listOrphans,
  purgeGuests,
  type ConsoleOverview,
} from '../api/console'
import { QueryError, QueryPending } from '../components/QueryStates'
import { BTN_DANGER, BTN_QUIET, EYEBROW, H1, H2, META, SUB } from '../ui'

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = n / 1024
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`
}

/** Key/value rows with a hairline between. */
function Rows({ entries }: { entries: [string, React.ReactNode][] }) {
  return (
    <dl className="divide-y divide-line">
      {entries.map(([k, v]) => (
        <div key={k} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-2.5">
          <dt className="text-[15px] text-mist-500">{k}</dt>
          <dd className="text-[15px] break-all text-mist-50">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="surface p-5 sm:p-6">
      <h2 className={H2}>{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  )
}

/** On/off pill. Violet reads as on; grey as off — never red, which is reserved. */
function Flag({ on, label }: { on: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 border px-2.5 py-1 text-[14px] ${
        on
          ? 'border-violet-500/50 bg-violet-900 text-violet-200'
          : 'border-line bg-ink-900 text-mist-500'
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${on ? 'bg-violet-300' : 'bg-mist-500'}`} />
      {label}
    </span>
  )
}

/** Two-step button: the second click is the confirmation. */
function ConfirmButton({
  idle,
  confirm,
  busy,
  pending,
  onConfirm,
}: {
  idle: string
  confirm: string
  busy: string
  pending: boolean
  onConfirm: () => void
}) {
  const [armed, setArmed] = useState(false)

  if (pending) {
    return <button type="button" disabled className={BTN_DANGER}>{busy}</button>
  }

  if (!armed) {
    return (
      <button type="button" onClick={() => setArmed(true)} className={BTN_DANGER}>
        {idle}
      </button>
    )
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => {
          setArmed(false)
          onConfirm()
        }}
        className={BTN_DANGER}
      >
        {confirm}
      </button>
      <button type="button" onClick={() => setArmed(false)} className={BTN_QUIET}>
        Cancel
      </button>
    </span>
  )
}

export default function Console() {
  const queryClient = useQueryClient()
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe })

  const overview = useQuery({
    queryKey: ['console', 'overview'],
    queryFn: getOverview,
    enabled: me?.role === 'admin',
    refetchInterval: 15_000,
  })

  const orphans = useQuery({
    queryKey: ['console', 'orphans'],
    queryFn: listOrphans,
    enabled: me?.role === 'admin',
  })

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['console'] })
    void queryClient.invalidateQueries({ queryKey: ['admin'] })
  }

  const purge = useMutation({ mutationFn: purgeGuests, onSuccess: invalidate })
  const sweep = useMutation({ mutationFn: deleteOrphans, onSuccess: invalidate })

  if (me && me.role !== 'admin') {
    return (
      <div className="mx-auto max-w-3xl animate-rise-in">
        <QueryError
          title="Not Authorized"
          message="The operations console is restricted to administrators."
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl animate-rise-in">
      <h1 className={H1}>Console</h1>
      <p className={SUB}>
        The state of this deployment. Separate from Admin, which manages people.
      </p>

      {overview.isPending && <div className="mt-10"><QueryPending label="Reading system state…" /></div>}

      {overview.isError && (
        <div className="mt-10">
          <QueryError title="Could not read system state" message={(overview.error as Error).message} />
        </div>
      )}

      {overview.isSuccess && (
        <div className="mt-8 space-y-3">
          <Card title="Runtime">
            <Rows
              entries={[
                ['Environment', <RuntimeEnv key="e" data={overview.data} />],
                ['Python', overview.data.runtime.python],
                ['Platform', overview.data.runtime.platform],
                ['Timezone', overview.data.runtime.timezone],
                ['Process', `pid ${overview.data.runtime.pid}`],
              ]}
            />
          </Card>

          <Card title="Scheduler">
            {/* Enabled and running are different things: on a sleeping free
                instance the config says yes and the process is not there. */}
            <div className="flex flex-wrap gap-2">
              <Flag on={overview.data.scheduler.enabled} label="Enabled in config" />
              <Flag on={Boolean(overview.data.scheduler.running)} label="Running now" />
            </div>
            <div className="mt-4">
              <Rows
                entries={[
                  ['Jobs registered', overview.data.scheduler.total_jobs ?? '—'],
                  ...(overview.data.scheduler.error
                    ? ([['Error', overview.data.scheduler.error]] as [string, React.ReactNode][])
                    : []),
                ]}
              />
            </div>
            {overview.data.scheduler.enabled && !overview.data.scheduler.running && (
              <p className="mt-3 text-[15px] text-danger-soft">
                Configured to run but not running — scheduled posts will not fire.
              </p>
            )}
          </Card>

          <Card title="Database">
            <Rows
              entries={[
                ['Backend', overview.data.database.backend],
                ['Users', overview.data.database.users.total],
                ['Awaiting approval', overview.data.database.users.pending_approval],
                ['Guests', overview.data.database.users.guests],
                ['Posts', overview.data.database.posts.total],
                ['Audit events', overview.data.database.audit_events],
              ]}
            />
            {Object.keys(overview.data.database.posts.by_status).length > 0 && (
              <div className="mt-4">
                <p className={EYEBROW}>Posts by status</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(overview.data.database.posts.by_status).map(([s, n]) => (
                    <span key={s} className="border border-line bg-ink-900 px-2.5 py-1 text-[14px] text-mist-200">
                      {s} · {n}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </Card>

          <Card title="Storage">
            <Rows
              entries={[
                ['Reels', `${overview.data.storage.reels.files} files · ${formatBytes(overview.data.storage.reels.bytes)}`],
                ['Uploads (temp)', `${overview.data.storage.uploads.files} files · ${formatBytes(overview.data.storage.uploads.bytes)}`],
                ...(overview.data.storage.disk
                  ? ([['Disk free', formatBytes(overview.data.storage.disk.free)]] as [string, React.ReactNode][])
                  : []),
              ]}
            />

            <div className="mt-5 border-t border-line pt-5">
              <p className="text-[15px] text-mist-200">Orphaned files</p>
              <p className={`${META} mt-1`}>
                Reels on disk that no post refers to — usually left by a deleted post.
              </p>
              {orphans.isPending && <p className={`${META} mt-3`}>Scanning…</p>}
              {orphans.isError && (
                <p className="mt-3 text-[15px] text-danger-soft">
                  {(orphans.error as Error).message}
                </p>
              )}
              {orphans.isSuccess && (
                <div className="mt-3">
                  <p className="text-[15px] text-mist-50">
                    {orphans.data.count} file(s) · {formatBytes(orphans.data.bytes)}
                  </p>
                  {orphans.data.count > 0 && (
                    <div className="mt-3">
                      <ConfirmButton
                        idle={`Delete ${orphans.data.count} orphaned file(s)`}
                        confirm="Yes, delete them"
                        busy="Deleting…"
                        pending={sweep.isPending}
                        onConfirm={() => sweep.mutate()}
                      />
                    </div>
                  )}
                  {sweep.isSuccess && (
                    <p className="mt-3 text-[15px] text-violet-300">
                      Deleted {sweep.data.deleted} file(s), freed {formatBytes(sweep.data.bytes)}.
                    </p>
                  )}
                  {sweep.isError && (
                    <p className="mt-3 text-[15px] text-danger-soft">
                      {(sweep.error as Error).message}
                    </p>
                  )}
                </div>
              )}
            </div>
          </Card>

          <Card title="Features">
            <div className="flex flex-wrap gap-2">
              {Object.entries(overview.data.features).map(([key, on]) => (
                <Flag key={key} on={on} label={key.replace(/_/g, ' ')} />
              ))}
            </div>
            {!overview.data.features.admin_allowlist_pinned && (
              <p className="mt-4 text-[15px] text-mist-500">
                No admin allowlist is pinned, so the first account on an empty database
                would become an administrator. Run{' '}
                <code className="border border-line bg-ink-800 px-1.5 py-0.5 text-[14px]">
                  python -m backend.admin_cli pin
                </code>{' '}
                to close that.
              </p>
            )}
          </Card>

          <Card title="Maintenance">
            <p className="text-[15px] text-mist-500">
              Guest accounts accumulate one per visitor. Purging removes them and
              everything they uploaded.
            </p>
            <div className="mt-4">
              <ConfirmButton
                idle={`Purge ${overview.data.database.users.guests} guest account(s)`}
                confirm="Yes, purge them"
                busy="Purging…"
                pending={purge.isPending}
                onConfirm={() => purge.mutate()}
              />
            </div>
            {purge.isSuccess && (
              <p className="mt-3 text-[15px] text-violet-300">
                Removed {purge.data.deleted_accounts} account(s) and{' '}
                {purge.data.deleted_posts} post(s).
              </p>
            )}
            {purge.isError && (
              <p className="mt-3 text-[15px] text-danger-soft">
                {(purge.error as Error).message}
              </p>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

/** Production with debug on is worth shouting about. */
function RuntimeEnv({ data }: { data: ConsoleOverview }) {
  const risky = data.runtime.environment === 'production' && data.runtime.debug
  return (
    <span className={risky ? 'text-danger-soft' : undefined}>
      {data.runtime.environment}
      {data.runtime.debug && ' · debug on'}
      {risky && ' — debug should be off in production'}
    </span>
  )
}
