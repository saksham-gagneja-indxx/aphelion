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

/** Definition row: 12px vertical rhythm, hairline separator between entries. */
const DEF_ROW =
  'flex items-center justify-between border-b border-lilac-50/[0.05] py-3'
const LAST_DEF_ROW = 'flex items-center justify-between py-3'

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
      <h1 className="font-display text-[34px] leading-tight font-bold tracking-[-.03em] text-lilac-50">
        Settings
      </h1>
      <p className="mt-2 text-[14.5px] text-lilac-50/50">
        Account and connection configuration
      </p>

      <div className="mt-[30px] space-y-5">
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
              <div className="glass overflow-hidden rounded-[18px]">
                <div className="flex items-center justify-between border-b border-lilac-50/[0.07] px-5 py-4">
                  <h2 className="text-sm font-semibold text-lilac-50">Instagram Connection</h2>
                  <span
                    className={`inline-flex items-center gap-[7px] rounded-pill border px-3 py-1 text-xs font-semibold ${
                      isConnected && instagramConfigured
                        ? 'border-status-posted/30 bg-status-posted/[0.12] text-[#6EE7B7]'
                        : instagramConfigured
                          ? 'border-status-cancelled/30 bg-status-cancelled/[0.12] text-[#FCD34D]'
                          : 'border-status-failed/[0.3] bg-status-failed/[0.12] text-[#FDA4AF]'
                    }`}
                  >
                    <span
                      className={`inline-block h-1.5 w-1.5 rounded-full ${
                        isConnected && instagramConfigured
                          ? 'bg-status-posted'
                          : instagramConfigured
                            ? 'bg-status-cancelled'
                            : 'bg-status-failed'
                      }`}
                    />
                    {isConnected && instagramConfigured
                      ? 'Connected'
                      : instagramConfigured
                        ? 'Configured'
                        : 'Not connected'}
                  </span>
                </div>

                <div className="px-5 py-1.5">
                  <dl className="text-[13.5px]">
                    <div className={DEF_ROW}>
                      <dt className="text-lilac-50/50">Username</dt>
                      <dd className="font-semibold text-lilac-50">
                        {username ? `@${username}` : '—'}
                      </dd>
                    </div>
                    {accountName && (
                      <div className={DEF_ROW}>
                        <dt className="text-lilac-50/50">Account name</dt>
                        <dd className="font-semibold text-lilac-50">{accountName}</dd>
                      </div>
                    )}
                    <div className={DEF_ROW}>
                      <dt className="text-lilac-50/50">Credentials in .env</dt>
                      <dd className="font-semibold text-lilac-50">
                        {instagramConfigured ? 'Yes' : 'No'}
                      </dd>
                    </div>
                    <div className={DEF_ROW}>
                      <dt className="text-lilac-50/50">Authenticated</dt>
                      <dd className="font-semibold text-lilac-50">
                        {isConnected ? 'Yes' : 'No'}
                      </dd>
                    </div>
                    {lastLogin && (
                      <div className={LAST_DEF_ROW}>
                        <dt className="text-lilac-50/50">Last login</dt>
                        <dd className="text-lilac-50/72">
                          {new Date(lastLogin).toLocaleString()}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>

                <div className="flex items-center gap-3.5 border-t border-lilac-50/[0.07] bg-ink-950/30 px-5 py-3.5">
                  <button
                    type="button"
                    onClick={handleReconnect}
                    className="rounded-pill bg-[linear-gradient(180deg,#AA3BFF,#7E14FF)] px-[18px] py-[9px] text-[13px] font-semibold text-white shadow-[0_4px_18px_rgba(134,59,255,.35)] transition hover:brightness-110"
                  >
                    Reconnect Instagram
                  </button>
                  <span className="text-xs text-lilac-50/32">Phase 2 — shows alert for now</span>
                </div>
              </div>

              {/* General settings */}
              {timezone && (
                <div className="glass overflow-hidden rounded-[18px]">
                  <div className="border-b border-lilac-50/[0.07] px-5 py-4">
                    <h2 className="text-sm font-semibold text-lilac-50">General</h2>
                  </div>
                  <div className="px-5 pt-1.5 pb-3.5">
                    <dl className="text-[13.5px]">
                      <div className={DEF_ROW}>
                        <dt className="text-lilac-50/50">Timezone</dt>
                        <dd className="font-semibold text-lilac-50">{timezone}</dd>
                      </div>
                      <div className={LAST_DEF_ROW}>
                        <dt className="text-lilac-50/50">User ID</dt>
                        <dd className="text-lilac-50/72">{USER_ID}</dd>
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
