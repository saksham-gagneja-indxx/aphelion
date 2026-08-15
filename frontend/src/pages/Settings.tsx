/**
 * Settings page — built by the antigravity session (Hour 12–18 sprint).
 * Error-state hardening: Hour 21–23 (antigravity session).
 *
 * Shows Instagram connection status from GET /api/status (instagram_configured flag)
 * and GET /api/users/1 (username + account details).
 * Now also shows LinkedIn connection status.
 */
import { useQuery } from '@tanstack/react-query'
import { getStatus, getUser } from '../api/client'
import { getLinkedInStatus, API_BASE } from '../api/auth'
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
    retry: 1,
  })

  const linkedinQuery = useQuery({
    queryKey: ['linkedin', USER_ID],
    queryFn: () => getLinkedInStatus(USER_ID),
    retry: 1,
  })

  const handleReconnectInstagram = () => {
    alert('Reconnect flow — Phase 2\n\nReal Instagram re-authentication will be wired in the next sprint.')
  }

  const anyError = statusQuery.isError || userQuery.isError || linkedinQuery.isError
  const anyPending = statusQuery.isPending || userQuery.isPending || linkedinQuery.isPending
  const allSuccess = statusQuery.isSuccess && userQuery.isSuccess && linkedinQuery.isSuccess

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
      <p className="mt-1 text-sm text-slate-500">
        Account and connection configuration
      </p>

      <div className="mt-8 space-y-6">
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
            {linkedinQuery.isError && !statusQuery.isError && !userQuery.isError && (
              <QueryError
                title="Could not load LinkedIn status"
                message={(linkedinQuery.error as Error).message}
              />
            )}
          </>
        )}

        {!anyError && anyPending && (
          <QueryPending label="Loading connection status…" />
        )}

        {allSuccess && (() => {
          const instagramConfigured = statusQuery.data.instagram_configured
          const username = userQuery.data.instagram_username
          const isConnected = userQuery.data.instagram_connected
          const lastLogin = userQuery.data.last_login
          const timezone = userQuery.data.timezone
          const accountName = userQuery.data.account_name

          const li = linkedinQuery.data

          return (
            <>
              {/* LinkedIn connection card (Primary) */}
              <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-100 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-slate-900">LinkedIn Connection</h2>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        li.connected
                          ? li.token_expired
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-emerald-100 text-emerald-800'
                          : 'bg-slate-100 text-slate-800'
                      }`}
                    >
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${
                          li.connected
                            ? li.token_expired
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                            : 'bg-slate-500'
                        }`}
                      />
                      {li.connected
                        ? li.token_expired
                          ? 'Token expired'
                          : 'Connected'
                        : 'Not connected'}
                    </span>
                  </div>
                </div>

                <div className="px-5 py-4">
                  <dl className="space-y-3 text-sm">
                    <div className="flex items-center justify-between">
                      <dt className="text-slate-500">Email</dt>
                      <dd className="font-medium text-slate-900">
                        {li.email ? li.email : '—'}
                      </dd>
                    </div>
                    {li.person_urn && (
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Person URN</dt>
                        <dd className="font-medium text-slate-900">{li.person_urn}</dd>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <dt className="text-slate-500">App Configured</dt>
                      <dd className="font-medium text-slate-900">
                        {li.app_configured ? 'Yes' : 'No'}
                      </dd>
                    </div>
                    {li.token_expires_at && (
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Token Expires</dt>
                        <dd className={`font-medium ${li.token_expired ? 'text-amber-600' : 'text-slate-700'}`}>
                          {new Date(li.token_expires_at).toLocaleString()}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>

                <div className="border-t border-slate-100 px-5 py-3">
                  <button
                    type="button"
                    onClick={() => { window.location.href = `${API_BASE}/api/auth/linkedin/start` }}
                    className="rounded-md bg-[#0a66c2] px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-[#004182] transition"
                  >
                    Reconnect LinkedIn
                  </button>
                </div>
              </div>

              {/* Instagram connection card (Phase 2 stub) */}
              <details className="group rounded-xl border border-slate-200 bg-white shadow-sm open:pb-1">
                <summary className="flex cursor-pointer items-center justify-between border-b border-slate-100 px-5 py-4 font-semibold text-slate-900 marker:content-none">
                  <span className="text-sm">Other platforms (Instagram)</span>
                  <span className="text-slate-400 transition group-open:rotate-180">
                    <svg fill="none" height="24" shapeRendering="geometricPrecision" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" viewBox="0 0 24 24" width="24"><path d="M6 9l6 6 6-6"></path></svg>
                  </span>
                </summary>
                
                <div>
                  <div className="border-b border-slate-100 px-5 py-4 bg-slate-50">
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
                      onClick={handleReconnectInstagram}
                      className="rounded-md bg-slate-800 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-slate-900 transition"
                    >
                      Reconnect Instagram
                    </button>
                    <span className="ml-3 text-xs text-slate-400">Phase 2 — shows alert for now</span>
                  </div>
                </div>
              </details>

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
