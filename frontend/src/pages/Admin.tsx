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
      <div className="mx-auto max-w-3xl">
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
    <div className="mx-auto max-w-5xl space-y-10">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Admin Panel</h1>
        <p className="mt-1 text-sm text-slate-500">Manage users and view system activity.</p>
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
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 bg-slate-50 px-5 py-4">
              <h2 className="text-sm font-semibold text-slate-900">Users</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-700">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="px-5 py-3 font-medium">Name</th>
                    <th className="px-5 py-3 font-medium">Email</th>
                    <th className="px-5 py-3 font-medium">Role</th>
                    <th className="px-5 py-3 font-medium">LinkedIn</th>
                    <th className="px-5 py-3 font-medium">Posts</th>
                    <th className="px-5 py-3 font-medium">Last Seen</th>
                    <th className="px-5 py-3 font-medium text-right">Active</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {usersQuery.data.users.map((user: AdminUser) => (
                    <tr key={user.id} className="hover:bg-slate-50">
                      <td className="px-5 py-4 font-medium text-slate-900">{user.name}</td>
                      <td className="px-5 py-4 text-slate-500">{user.email}</td>
                      <td className="px-5 py-4">
                        <select
                          value={user.role}
                          onChange={(e) =>
                            roleMutation.mutate({
                              id: user.id,
                              role: e.target.value as 'admin' | 'operator',
                            })
                          }
                          disabled={user.id === me.id || roleMutation.isPending}
                          className="rounded-md border border-slate-300 bg-white py-1 px-2 text-xs shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
                        >
                          <option value="operator">Operator</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td className="px-5 py-4">
                        {user.linkedin_connected ? (
                          <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                            Connected
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-slate-500">{user.post_count}</td>
                      <td className="px-5 py-4 text-slate-500 text-xs">
                        {user.last_seen_at
                          ? new Date(user.last_seen_at).toLocaleString()
                          : 'Never'}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <button
                          type="button"
                          onClick={() =>
                            activeMutation.mutate({
                              id: user.id,
                              is_active: !user.is_active,
                            })
                          }
                          disabled={user.id === me.id || activeMutation.isPending}
                          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 disabled:opacity-50 ${
                            user.is_active ? 'bg-indigo-600' : 'bg-slate-200'
                          }`}
                        >
                          <span className="sr-only">Use setting</span>
                          <span
                            aria-hidden="true"
                            className={`pointer-events-none absolute left-0.5 inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                              user.is_active ? 'translate-x-4' : 'translate-x-0'
                            }`}
                          />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 bg-slate-50 px-5 py-4 flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-900">Audit Log</h2>
            </div>
            {auditQuery.data.events.length === 0 ? (
              <div className="p-6 text-center text-sm text-slate-500">No events found.</div>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {auditQuery.data.events.map((event) => (
                  <li key={event.id} className="flex items-start gap-4 p-4 hover:bg-slate-50">
                    <div className="min-w-0 flex-1">
                      <p className="text-slate-900">
                        <span className="font-medium">{event.actor_name}</span>{' '}
                        {event.action}{' '}
                        <span className="font-medium text-slate-700">{event.target}</span>
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {new Date(event.created_at).toLocaleString()}
                      </p>
                    </div>
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
