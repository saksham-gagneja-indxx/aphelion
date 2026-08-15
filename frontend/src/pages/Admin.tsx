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
        <h1 className="font-display text-[34px] leading-tight font-bold tracking-[-.03em] text-lilac-50">
          Admin Panel
        </h1>
        <p className="mt-2 text-[14.5px] text-lilac-50/50">
          Manage users and view system activity.
        </p>
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
          <div className="glass overflow-hidden rounded-[18px]">
            <div className="border-b border-lilac-50/[0.07] bg-ink-950/35 px-5 py-4">
              <h2 className="text-sm font-semibold text-lilac-50">Users</h2>
            </div>
            {/* The <table> is a grid here so the columns stay aligned without
                table styling — see the handoff, Admin section. */}
            <div className="overflow-x-auto">
              <div className="min-w-[900px]">
                <div
                  className={`${GRID_COLS} border-b border-lilac-50/[0.07] px-5 py-3 text-[11px] font-semibold uppercase tracking-[.12em] text-lilac-50/38`}
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
                    className={`${GRID_COLS} items-center px-5 py-4 transition hover:bg-lilac-50/[0.03]`}
                  >
                    <span className="text-[13.5px] font-semibold text-lilac-50">{user.name}</span>
                    <span className="truncate pr-3 text-[13.5px] text-lilac-50/50">
                      {user.email}
                    </span>
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
                        className="rounded-[9px] border border-lilac-50/[0.12] bg-ink-950/50 px-[11px] py-[5px] text-xs text-lilac-50 transition focus:border-violet-400 focus:shadow-[0_0_0_3px_rgba(170,59,255,.15)] focus:outline-none disabled:opacity-50"
                      >
                        <option value="operator">Operator</option>
                        <option value="admin">Admin</option>
                      </select>
                    </span>
                    <span>
                      {user.linkedin_connected ? (
                        <span className="inline-flex items-center rounded-pill border border-status-posted/30 bg-status-posted/[0.13] px-2.5 py-[3px] text-[11.5px] font-semibold text-[#6EE7B7]">
                          Connected
                        </span>
                      ) : (
                        <span className="text-lilac-50/35">—</span>
                      )}
                    </span>
                    <span className="text-[13.5px] text-lilac-50/50">{user.post_count}</span>
                    <span className="text-xs text-lilac-50/45">
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
                        className={`relative inline-flex h-[21px] w-[38px] shrink-0 cursor-pointer items-center rounded-pill p-0.5 transition disabled:opacity-50 ${
                          user.is_active
                            ? 'bg-[linear-gradient(180deg,#AA3BFF,#7E14FF)] shadow-[0_0_12px_rgba(134,59,255,.5)]'
                            : 'bg-lilac-50/10'
                        }`}
                      >
                        <span className="sr-only">Use setting</span>
                        <span
                          aria-hidden="true"
                          className={`pointer-events-none inline-block h-[17px] w-[17px] rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,.4)] transition duration-200 ease-in-out ${
                            user.is_active ? 'translate-x-[17px]' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="glass overflow-hidden rounded-[18px]">
            <div className="flex items-center justify-between border-b border-lilac-50/[0.07] bg-ink-950/35 px-5 py-4">
              <h2 className="text-sm font-semibold text-lilac-50">Audit Log</h2>
            </div>
            {auditQuery.data.events.length === 0 ? (
              <div className="p-6 text-center text-[13.5px] text-lilac-50/45">No events found.</div>
            ) : (
              <ul className="divide-y divide-lilac-50/[0.05]">
                {auditQuery.data.events.map((event) => (
                  <li key={event.id} className="px-5 py-3.5 transition hover:bg-lilac-50/[0.03]">
                    <p className="text-[13.5px] text-lilac-50/78">
                      <span className="font-semibold text-lilac-50">{event.actor_name}</span>{' '}
                      {/* Cancellations read as destructive, so they get the
                          amber treatment instead of the default lilac. */}
                      <span
                        className={`font-medium ${
                          event.action.includes('cancel')
                            ? 'text-[#FCD34D]'
                            : 'text-lilac-300/90'
                        }`}
                      >
                        {event.action}
                      </span>{' '}
                      <span className="font-semibold text-lilac-50/60">{event.target}</span>
                    </p>
                    <p className="mt-1.5 text-[11.5px] text-lilac-50/32">
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
