/**
 * Settings page — built by the antigravity session (Hour 12–18 sprint).
 * Error-state hardening: Hour 21–23 (antigravity session).
 *
 * Shows Instagram connection status from GET /api/status (instagram_configured flag)
 * and GET /api/users/1 (username + account details).
 * Now also shows LinkedIn connection status.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getStatus, getUser } from '../api/client'
import { getLinkedInStatus, getLinkedInAuthorizeUrl, openBlankTab } from '../api/auth'
import { QueryError, QueryPending } from '../components/QueryStates'
import { BTN_PRIMARY, H1, H2, META, SUB } from '../ui'
import { useUserId } from '../current-user'

/** Definition row: hairline separator between entries, none after the last. */
const DEF_ROW = 'flex items-center justify-between border-b border-line py-3.5'
const LAST_DEF_ROW = 'flex items-center justify-between py-3.5'

export default function Settings() {
  const USER_ID = useUserId()
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

  const [reconnectError, setReconnectError] = useState<string | null>(null)

  /**
   * Re-connect runs in a new tab, leaving this page in place.
   *
   * The tab is claimed synchronously because popup blockers only permit
   * window.open inside a user gesture, and the URL has to be fetched first:
   * /start needs the bearer token, so navigating to it directly returns 401.
   * That was the previous behaviour and the button never worked.
   */
  const handleReconnectLinkedIn = async () => {
    setReconnectError(null)
    const tab = openBlankTab()
    try {
      const url = await getLinkedInAuthorizeUrl()
      if (tab) {
        tab.location.href = url
      } else {
        window.location.href = url
      }
    } catch (err) {
      tab?.close()
      setReconnectError((err as Error).message)
    }
  }

  const anyError = statusQuery.isError || userQuery.isError || linkedinQuery.isError
  const anyPending = statusQuery.isPending || userQuery.isPending || linkedinQuery.isPending
  const allSuccess = statusQuery.isSuccess && userQuery.isSuccess && linkedinQuery.isSuccess

  return (
    <div className="mx-auto max-w-2xl animate-rise-in">
      <h1 className={H1}>Settings</h1>
      <p className={SUB}>Account and connection configuration</p>

      <div className="mt-10 space-y-3">
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
              <div className="surface">
                <div className="flex items-center justify-between border-b border-line px-5 py-4">
                  <h2 className={H2}>LinkedIn Connection</h2>
                  {/* Connected fills violet; an expired token blocks publishing,
                      so it takes the danger hue rather than a third violet. */}
                  <span
                    className={`inline-flex items-center gap-2 border px-3 py-1 text-[14px] ${
                      li.connected
                        ? li.token_expired
                          ? 'border-danger/45 bg-danger/[0.1] text-danger-soft'
                          : 'border-violet-500/50 bg-violet-900 text-violet-200'
                        : 'border-line bg-ink-900 text-mist-500'
                    }`}
                  >
                    <span
                      className={`inline-block h-1.5 w-1.5 rounded-full ${
                        li.connected
                          ? li.token_expired
                            ? 'bg-danger'
                            : 'bg-violet-300'
                          : 'bg-mist-500'
                      }`}
                    />
                    {li.connected
                      ? li.token_expired
                        ? 'Token expired'
                        : 'Connected'
                      : 'Not connected'}
                  </span>
                </div>

                <div className="px-5 py-1">
                  <dl className="text-[16px]">
                    <div className={DEF_ROW}>
                      <dt className="text-mist-500">Email</dt>
                      <dd className="text-mist-50">{li.email ? li.email : '—'}</dd>
                    </div>
                    {li.person_urn && (
                      <div className={DEF_ROW}>
                        <dt className="text-mist-500">Person URN</dt>
                        <dd className="truncate pl-4 text-mist-50">{li.person_urn}</dd>
                      </div>
                    )}
                    <div className={li.token_expires_at ? DEF_ROW : LAST_DEF_ROW}>
                      <dt className="text-mist-500">App Configured</dt>
                      <dd className="text-mist-50">{li.app_configured ? 'Yes' : 'No'}</dd>
                    </div>
                    {li.token_expires_at && (
                      <div className={LAST_DEF_ROW}>
                        <dt className="text-mist-500">Token Expires</dt>
                        <dd className={li.token_expired ? 'text-danger-soft' : 'text-mist-200'}>
                          {new Date(li.token_expires_at).toLocaleString()}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>

                <div className="border-t border-line bg-ink-950 px-5 py-4">
                  <button
                    type="button"
                    onClick={() => void handleReconnectLinkedIn()}
                    className={BTN_PRIMARY}
                  >
                    Reconnect LinkedIn
                  </button>
                  {reconnectError && (
                    <p className="mt-3 text-[14px] text-danger-soft">{reconnectError}</p>
                  )}
                </div>
              </div>

              {/* Instagram connection card (Phase 2 stub) */}
              <details className="surface group">
                <summary className="flex cursor-pointer items-center justify-between px-5 py-4 marker:content-none group-open:border-b group-open:border-line">
                  <span className={H2}>Other platforms (Instagram)</span>
                  <span className="text-mist-500 transition group-open:rotate-180">
                    <svg fill="none" height="24" shapeRendering="geometricPrecision" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" viewBox="0 0 24 24" width="24"><path d="M6 9l6 6 6-6"></path></svg>
                  </span>
                </summary>
                
                <div>
                  <div className="flex items-center justify-between border-b border-line bg-ink-950 px-5 py-4">
                    <h2 className={H2}>Instagram Connection</h2>
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
                        <dd className="text-mist-50">{username ? `@${username}` : '—'}</dd>
                      </div>
                      {accountName && (
                        <div className={DEF_ROW}>
                          <dt className="text-mist-500">Account name</dt>
                          <dd className="text-mist-50">{accountName}</dd>
                        </div>
                      )}
                      <div className={DEF_ROW}>
                        <dt className="text-mist-500">Credentials in .env</dt>
                        <dd className="text-mist-50">{instagramConfigured ? 'Yes' : 'No'}</dd>
                      </div>
                      <div className={lastLogin ? DEF_ROW : LAST_DEF_ROW}>
                        <dt className="text-mist-500">Authenticated</dt>
                        <dd className="text-mist-50">{isConnected ? 'Yes' : 'No'}</dd>
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
                    <button
                      type="button"
                      onClick={handleReconnectInstagram}
                      className={BTN_PRIMARY}
                    >
                      Reconnect Instagram
                    </button>
                    <span className={META}>Phase 2 — shows alert for now</span>
                  </div>
                </div>
              </details>

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
