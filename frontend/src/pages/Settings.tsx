/**
 * Settings page — built by the antigravity session (Hour 12–18 sprint).
 * Error-state hardening: Hour 21–23 (antigravity session).
 *
 * Shows Instagram connection status from GET /api/status (instagram_configured flag)
 * and GET /api/users/1 (username + account details).
 *
 * "Reconnect" button shows an alert — real reconnect flow is Phase 2 per TIMELINE.md.
 * .env update UI is explicitly out of scope for v1.
 *
 * Query-state branches are exhaustive:
 *   anyError → anyPending → bothSuccess+data
 *
 * The entire connection card is hidden until both queries succeed, so a dead
 * backend never renders as "Not connected" with Username "—" — that looks like
 * a real answer when it's actually an outage.
 */
import { useQuery } from '@tanstack/react-query'
import { getStatus, getUser } from '../api/client'
import { QueryError, QueryPending } from '../components/QueryStates'

const USER_ID = 1

export default function Settings() {
  const statusQuery = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
  })

  const userQuery = useQuery({
    queryKey: ['user', USER_ID],
    queryFn: () => getUser(USER_ID),
    // Don't retry aggressively — user 1 might not exist yet
    retry: 1,
  })

  const handleReconnect = () => {
    alert('Reconnect flow — Phase 2\n\nReal Instagram re-authentication will be wired in the next sprint.')
  }

  // --- Derive composite states ---
  // Either query failing should surface an error banner, not fall through
  // to the data card with default falsy values.
  const anyError = statusQuery.isError || userQuery.isError
  // Use isPending (not isLoading): during retry backoff a query is pending
  // with fetchStatus "idle", so isLoading is false and gating on it can
  // leave a blank section.
  const anyPending = statusQuery.isPending || userQuery.isPending
  const bothSuccess = statusQuery.isSuccess && userQuery.isSuccess

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
      <p className="mt-1 text-sm text-slate-500">
        Account and connection configuration
      </p>

      <div className="mt-8 space-y-6">
        {/* --- Error state (first branch — never fall through to data) --- */}
        {anyError && (
          <>
            {statusQuery.isError && (
              <QueryError
                title="Could not reach backend"
                message="Make sure the Flask server is running on the expected port."
              />
            )}
            {userQuery.isError && !statusQuery.isError && (
              <QueryError
                title="User not found"
                message={`User ID ${USER_ID} doesn't exist yet. Create a user via POST /api/users first.`}
              />
            )}
          </>
        )}

        {/* --- Pending state (second branch) --- */}
        {!anyError && anyPending && (
          <QueryPending label="Loading connection status…" />
        )}

        {/* --- Data state: only render when BOTH queries succeeded ---
            This ensures a dead backend never renders as "Not connected"
            with Username "—" — which looks like a valid answer. */}
        {bothSuccess && (() => {
          const instagramConfigured = statusQuery.data.instagram_configured
          const username = userQuery.data.instagram_username
          const isConnected = userQuery.data.instagram_connected
          const lastLogin = userQuery.data.last_login
          const timezone = userQuery.data.timezone
          const accountName = userQuery.data.account_name

          return (
            <>
              {/* Instagram connection card */}
              <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-100 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-slate-900">Instagram Connection</h2>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        isConnected && instagramConfigured
                          ? 'bg-emerald-100 text-emerald-800'
                          : instagramConfigured
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-red-100 text-red-800'
                      }`}
                    >
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${
                          isConnected && instagramConfigured
                            ? 'bg-emerald-500'
                            : instagramConfigured
                              ? 'bg-amber-500'
                              : 'bg-red-500'
                        }`}
                      />
                      {isConnected && instagramConfigured
                        ? 'Connected'
                        : instagramConfigured
                          ? 'Configured'
                          : 'Not connected'}
                    </span>
                  </div>
                </div>

                <div className="px-5 py-4">
                  <dl className="space-y-3 text-sm">
                    <div className="flex items-center justify-between">
                      <dt className="text-slate-500">Username</dt>
                      <dd className="font-medium text-slate-900">
                        {username ? `@${username}` : '—'}
                      </dd>
                    </div>
                    {accountName && (
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Account name</dt>
                        <dd className="font-medium text-slate-900">{accountName}</dd>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <dt className="text-slate-500">Credentials in .env</dt>
                      <dd className="font-medium text-slate-900">
                        {instagramConfigured ? 'Yes' : 'No'}
                      </dd>
                    </div>
                    <div className="flex items-center justify-between">
                      <dt className="text-slate-500">Authenticated</dt>
                      <dd className="font-medium text-slate-900">
                        {isConnected ? 'Yes' : 'No'}
                      </dd>
                    </div>
                    {lastLogin && (
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Last login</dt>
                        <dd className="text-slate-700">
                          {new Date(lastLogin).toLocaleString()}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>

                <div className="border-t border-slate-100 px-5 py-3">
                  <button
                    type="button"
                    onClick={handleReconnect}
                    className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 transition"
                  >
                    Reconnect Instagram
                  </button>
                  <span className="ml-3 text-xs text-slate-400">Phase 2 — shows alert for now</span>
                </div>
              </div>

              {/* General settings */}
              {timezone && (
                <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-5 py-4">
                    <h2 className="text-sm font-semibold text-slate-900">General</h2>
                  </div>
                  <div className="px-5 py-4">
                    <dl className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Timezone</dt>
                        <dd className="font-medium text-slate-900">{timezone}</dd>
                      </div>
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">User ID</dt>
                        <dd className="font-mono text-slate-700">{USER_ID}</dd>
                      </div>
                    </dl>
                  </div>
                </div>
              )}
            </>
          )
        })()}
      </div>
    </div>
  )
}
