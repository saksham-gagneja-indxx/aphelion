import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMe } from '../api/auth'
import {
  getAuditLogs,
  getUsers,
  updateUserActive,
  updateUserRole,
  type AdminUser,
} from '../api/admin'
import { QueryError, QueryPending } from '../components/QueryStates'
import { EYEBROW, H1, H2, META, SUB } from '../ui'

/** Shared track for the users "table" — header and body rows must agree. */
const GRID_COLS = 'grid grid-cols-[1.5fr_1.8fr_1.1fr_1fr_.6fr_1.4fr_.7fr]'

export default function Admin() {
  const queryClient = useQueryClient()
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe })

  const usersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: getUsers,
    enabled: me?.role === 'admin',
  })

  const auditQuery = useQuery({
    queryKey: ['admin', 'audit'],
    queryFn: () => getAuditLogs(100),
    enabled: me?.role === 'admin',
  })

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: 'admin' | 'operator' }) =>
      updateUserRole(id, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'audit'] })
    },
  })

  const activeMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      updateUserActive(id, is_active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'audit'] })
    },
  })

  if (me?.role !== 'admin') {
    return (
      <div className="mx-auto max-w-3xl animate-rise-in">
        <QueryError
          title="Not Authorized"
          message="You do not have permission to view this page."
        />
      </div>
    )
  }

  const anyError = usersQuery.isError || auditQuery.isError
  const anyPending = usersQuery.isPending || auditQuery.isPending
  const bothSuccess = usersQuery.isSuccess && auditQuery.isSuccess

  return (
    <div className="mx-auto max-w-5xl animate-rise-in space-y-[22px]">
      <div>
        <h1 className={H1}>Admin Panel</h1>
        <p className={SUB}>Manage users and view system activity.</p>
      </div>

      {anyError && (
        <div className="space-y-4">
          {usersQuery.isError && (
            <QueryError
              title="Failed to load users"
              message={(usersQuery.error as Error).message}
            />
          )}
          {auditQuery.isError && !usersQuery.isError && (
            <QueryError
              title="Failed to load audit logs"
              message={(auditQuery.error as Error).message}
            />
          )}
        </div>
      )}

      {!anyError && anyPending && (
        <QueryPending label="Loading admin data…" />
      )}

      {bothSuccess && (
        <>
          <div className="surface">
            <div className="border-b border-line bg-ink-950 px-5 py-4">
              <h2 className={H2}>Users</h2>
            </div>
            {/* The <table> is a grid here so the columns stay aligned without
                table styling — see the handoff, Admin section. */}
            <div className="overflow-x-auto">
              <div className="min-w-[900px]">
                <div
                  className={`${GRID_COLS} ${EYEBROW} border-b border-line px-5 py-3`}
                >
                  <span>Name</span>
                  <span>Email</span>
                  <span>Role</span>
                  <span>LinkedIn</span>
                  <span>Posts</span>
                  <span>Last Seen</span>
                  <span className="text-right">Active</span>
                </div>
                {usersQuery.data.users.map((user: AdminUser) => (
                  <div
                    key={user.id}
                    className={`${GRID_COLS} items-center border-b border-line px-5 py-4 transition last:border-b-0 hover:bg-ink-800`}
                  >
                    <span className="text-[16px] text-mist-50">{user.name}</span>
                    <span className="truncate pr-3 text-[16px] text-mist-500">{user.email}</span>
                    <span>
                      <select
                        value={user.role}
                        onChange={(e) =>
                          roleMutation.mutate({
                            id: user.id,
                            role: e.target.value as 'admin' | 'operator',
                          })
                        }
                        disabled={user.id === me.id || roleMutation.isPending}
                        className="border border-line bg-ink-800 px-2.5 py-1 text-[14px] text-mist-50 transition focus:border-violet-500 focus:outline-none disabled:opacity-40"
                      >
                        <option value="operator">Operator</option>
                        <option value="admin">Admin</option>
                      </select>
                    </span>
                    <span>
                      {user.linkedin_connected ? (
                        <span className="inline-flex items-center border border-violet-500/50 bg-violet-900 px-2.5 py-0.5 text-[13px] text-violet-200">
                          Connected
                        </span>
                      ) : (
                        <span className="text-mist-500">—</span>
                      )}
                    </span>
                    <span className="text-[16px] text-mist-500">{user.post_count}</span>
                    <span className={META}>
                      {user.last_seen_at
                        ? new Date(user.last_seen_at).toLocaleString()
                        : 'Never'}
                    </span>
                    <span className="text-right">
                      <button
                        type="button"
                        onClick={() =>
                          activeMutation.mutate({
                            id: user.id,
                            is_active: !user.is_active,
                          })
                        }
                        disabled={user.id === me.id || activeMutation.isPending}
                        /* Square track, square knob — the system has no pills. */
                        className={`relative inline-flex h-5 w-10 shrink-0 cursor-pointer items-center border p-0.5 transition disabled:opacity-40 ${
                          user.is_active
                            ? 'border-violet-500 bg-violet-500'
                            : 'border-line bg-ink-800'
                        }`}
                      >
                        <span className="sr-only">Use setting</span>
                        <span
                          aria-hidden="true"
                          className={`pointer-events-none inline-block h-[14px] w-[14px] transition duration-200 ease-in-out ${
                            user.is_active
                              ? 'translate-x-[20px] bg-mist-50'
                              : 'translate-x-0 bg-mist-500'
                          }`}
                        />
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="surface">
            <div className="flex items-center justify-between border-b border-line bg-ink-950 px-5 py-4">
              <h2 className={H2}>Audit Log</h2>
            </div>
            {auditQuery.data.events.length === 0 ? (
              <div className="p-6 text-center text-[16px] text-mist-500">No events found.</div>
            ) : (
              <ul className="divide-y divide-line">
                {auditQuery.data.events.map((event) => (
                  <li key={event.id} className="px-5 py-4 transition hover:bg-ink-800">
                    <p className="text-[16px] text-mist-500">
                      <span className="text-mist-50">{event.actor_name}</span>{' '}
                      {/* Cancellations are destructive, so they read in the
                          danger hue rather than violet. */}
                      <span
                        className={
                          event.action.includes('cancel') ? 'text-danger-soft' : 'text-violet-300'
                        }
                      >
                        {event.action}
                      </span>{' '}
                      <span className="text-mist-200">{event.target}</span>
                    </p>
                    <p className={`${META} mt-1.5`}>
                      {new Date(event.created_at).toLocaleString()}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  )
}
