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
import { BTN_PRIMARY, H1, H2, META, SUB } from '../ui'

const USER_ID = 1

/** Definition row: hairline separator between entries, none after the last. */
const DEF_ROW = 'flex items-center justify-between border-b border-line py-3.5'
const LAST_DEF_ROW = 'flex items-center justify-between py-3.5'

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
    <div className="mx-auto max-w-2xl animate-rise-in">
      <h1 className={H1}>Settings</h1>
      <p className={SUB}>Account and connection configuration</p>

      <div className="mt-10 space-y-3">
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
              <div className="surface">
                <div className="flex items-center justify-between border-b border-line px-5 py-4">
                  <h2 className={H2}>Instagram Connection</h2>
                  {/* Three states, no three hues: connected fills violet,
                      configured outlines it, not-connected stays grey. */}
                  <span
                    className={`inline-flex items-center gap-2 border px-3 py-1 text-[14px] ${
                      isConnected && instagramConfigured
                        ? 'border-violet-500/50 bg-violet-900 text-violet-200'
                        : instagramConfigured
                          ? 'border-violet-500/40 bg-violet-500/[0.1] text-violet-300'
                          : 'border-line bg-ink-900 text-mist-500'
                    }`}
                  >
                    <span
                      className={`inline-block h-1.5 w-1.5 rounded-full ${
                        isConnected && instagramConfigured
                          ? 'bg-violet-300'
                          : instagramConfigured
                            ? 'bg-violet-500'
                            : 'bg-mist-500'
                      }`}
                    />
                    {isConnected && instagramConfigured
                      ? 'Connected'
                      : instagramConfigured
                        ? 'Configured'
                        : 'Not connected'}
                  </span>
                </div>

                <div className="px-5 py-1">
                  <dl className="text-[16px]">
                    <div className={DEF_ROW}>
                      <dt className="text-mist-500">Username</dt>
                      <dd className="text-mist-50">
                        {username ? `@${username}` : '—'}
                      </dd>
                    </div>
                    {accountName && (
                      <div className={DEF_ROW}>
                        <dt className="text-mist-500">Account name</dt>
                        <dd className="text-mist-50">{accountName}</dd>
                      </div>
                    )}
                    <div className={DEF_ROW}>
                      <dt className="text-mist-500">Credentials in .env</dt>
                      <dd className="text-mist-50">
                        {instagramConfigured ? 'Yes' : 'No'}
                      </dd>
                    </div>
                    <div className={DEF_ROW}>
                      <dt className="text-mist-500">Authenticated</dt>
                      <dd className="text-mist-50">
                        {isConnected ? 'Yes' : 'No'}
                      </dd>
                    </div>
                    {lastLogin && (
                      <div className={LAST_DEF_ROW}>
                        <dt className="text-mist-500">Last login</dt>
                        <dd className="text-mist-200">
                          {new Date(lastLogin).toLocaleString()}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>

                <div className="flex flex-wrap items-center gap-4 border-t border-line bg-ink-950 px-5 py-4">
                  <button type="button" onClick={handleReconnect} className={BTN_PRIMARY}>
                    Reconnect Instagram
                  </button>
                  <span className={META}>Phase 2 — shows alert for now</span>
                </div>
              </div>

              {/* General settings */}
              {timezone && (
                <div className="surface">
                  <div className="border-b border-line px-5 py-4">
                    <h2 className={H2}>General</h2>
                  </div>
                  <div className="px-5 pt-1 pb-3">
                    <dl className="text-[16px]">
                      <div className={DEF_ROW}>
                        <dt className="text-mist-500">Timezone</dt>
                        <dd className="text-mist-50">{timezone}</dd>
                      </div>
                      <div className={LAST_DEF_ROW}>
                        <dt className="text-mist-500">User ID</dt>
                        <dd className="text-mist-200">{USER_ID}</dd>
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
