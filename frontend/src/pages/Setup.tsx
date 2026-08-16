/**
 * Guided LinkedIn setup.
 *
 * The awkward part of this flow is that most of the work happens somewhere
 * else — in LinkedIn's developer portal — and people come back with no way to
 * know whether what they did worked. So each step is checked against real
 * state from /api/setup/state rather than asking "did that work?" and
 * believing the answer.
 *
 * While a step is open in another tab this polls every few seconds, so
 * returning to this tab shows the step already ticked rather than a button
 * asking them to confirm something the app can find out for itself.
 */
import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  clearLinkedInCredentials,
  getLinkedInAuthorizeUrl,
  getSetupState,
  linkedInLoginUrl,
  openBlankTab,
  saveLinkedInCredentials,
  type SetupStep,
} from '../api/auth'
import { QueryError, QueryPending } from '../components/QueryStates'
import { BTN_OUTLINE, BTN_PRIMARY, BTN_QUIET, FIELD, H1, H2, LABEL, SUB } from '../ui'

/**
 * Bring-your-own-LinkedIn-app form.
 *
 * The other half of the "app" step: instead of waiting on an administrator to
 * finish server-side setup, any account can paste its own Client ID/Secret
 * and publish through that instead. Saved encrypted (backend/utils/crypto.py)
 * and never echoed back - only the client id, which is not secret, is shown
 * once saved.
 */
function OwnAppForm({
  hasOwnApp,
  ownClientId,
  onChanged,
}: {
  hasOwnApp: boolean
  ownClientId: string | null
  onChanged: () => void
}) {
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (hasOwnApp) {
    return (
      <div className="mt-4 border border-line bg-ink-800 px-4 py-3.5">
        <p className="text-[15px] text-mist-200">
          Using your own app <span className="text-mist-500">({ownClientId})</span>
        </p>
        <button
          type="button"
          className={`${BTN_QUIET} mt-2`}
          disabled={busy}
          onClick={() => {
            setBusy(true)
            setError(null)
            void clearLinkedInCredentials()
              .then(onChanged)
              .catch((err: Error) => setError(err.message))
              .finally(() => setBusy(false))
          }}
        >
          {busy ? 'Removing…' : 'Remove and use the shared app instead'}
        </button>
        {error && <p className="mt-2 text-[14px] text-danger-soft">{error}</p>}
      </div>
    )
  }

  return (
    <form
      className="mt-4 space-y-3 border border-line bg-ink-800 px-4 py-4"
      onSubmit={(e) => {
        e.preventDefault()
        setBusy(true)
        setError(null)
        void saveLinkedInCredentials(clientId.trim(), clientSecret.trim())
          .then(() => {
            setClientId('')
            setClientSecret('')
            onChanged()
          })
          .catch((err: Error) => setError(err.message))
          .finally(() => setBusy(false))
      }}
    >
      <p className="text-[14px] text-mist-500">
        Or bring your own app instead of waiting on the server-wide one:
      </p>
      <div>
        <label className={LABEL} htmlFor="own-client-id">Client ID</label>
        <input
          id="own-client-id"
          className={FIELD}
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          required
        />
      </div>
      <div>
        <label className={LABEL} htmlFor="own-client-secret">Client Secret</label>
        <input
          id="own-client-secret"
          type="password"
          className={FIELD}
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          required
        />
      </div>
      {error && <p className="text-[14px] text-danger-soft">{error}</p>}
      <button type="submit" disabled={busy} className={BTN_OUTLINE}>
        {busy ? 'Saving…' : 'Save my app'}
      </button>
    </form>
  )
}

/** Copyable one-liner — the redirect URL has to match character for character. */
function Copyable({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const t = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(t)
  }, [copied])

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <code className="min-w-0 flex-1 truncate border border-line bg-ink-800 px-3 py-2 text-[14px] text-mist-200">
        {value}
      </code>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard?.writeText(value).then(() => setCopied(true))
        }}
        className={BTN_QUIET}
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}

function Tick({ done }: { done: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center border ${
        done
          ? 'border-violet-500 bg-violet-500 text-ink-950'
          : 'border-line bg-ink-900 text-mist-500'
      }`}
    >
      {done ? (
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-mist-500" />
      )}
    </span>
  )
}

/** Instructions per step. Kept here because they are UI copy, not server data. */
function StepBody({
  step,
  redirectUri,
  isAdmin,
  onConnect,
  connecting,
  hasOwnApp,
  ownClientId,
  onOwnAppChanged,
}: {
  step: SetupStep
  redirectUri: string
  isAdmin: boolean
  onConnect: () => void
  connecting: boolean
  hasOwnApp: boolean
  ownClientId: string | null
  onOwnAppChanged: () => void
}) {
  const text = 'text-[15px] leading-[1.65] text-mist-500'
  const strong = 'text-mist-200'

  switch (step.id) {
    case 'app':
      return (
        <div className={`${text} space-y-3`}>
          <p>
            Create an app in LinkedIn&rsquo;s developer portal. It needs a LinkedIn{' '}
            <span className={strong}>company page</span> — you can make one in a minute, and
            it does not have to be a real company.
          </p>
          {!isAdmin ? (
            <p>
              This part is done once, on the server. {step.detail}
            </p>
          ) : (
            <>
              <p>
                Afterwards copy the Client ID and Client Secret from the app&rsquo;s{' '}
                <span className={strong}>Auth</span> tab into <code>.env</code> as{' '}
                <code>LINKEDIN_CLIENT_ID</code> and <code>LINKEDIN_CLIENT_SECRET</code>, then
                restart the server.
              </p>
              <a
                href="https://www.linkedin.com/developers/apps/new"
                target="_blank"
                rel="noreferrer"
                className={`${BTN_PRIMARY} mt-1`}
              >
                Open LinkedIn developer portal
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3" />
                </svg>
              </a>
            </>
          )}
          <OwnAppForm hasOwnApp={hasOwnApp} ownClientId={ownClientId} onChanged={onOwnAppChanged} />
        </div>
      )

    case 'redirect':
      return (
        <div className={`${text} space-y-3`}>
          <p>
            On the app&rsquo;s <span className={strong}>Auth</span> tab, under{' '}
            <span className={strong}>Authorized redirect URLs</span>, add exactly this. A
            single character of difference — http vs https, a missing port, a trailing
            slash — and sign-in fails.
          </p>
          <Copyable value={redirectUri} />
          <p>
            This one cannot be checked from here: LinkedIn only reveals a mismatch by
            rejecting a real attempt. It ticks once a sign-in has actually come back
            through it, which is the proof.
          </p>
        </div>
      )

    case 'connect':
      return (
        <div className={`${text} space-y-3`}>
          <p>
            Authorize the app for your own account. Consent opens in a new tab and closes
            itself; this page notices and moves on.
          </p>
          <button
            type="button"
            onClick={onConnect}
            disabled={connecting}
            className={BTN_PRIMARY}
          >
            {connecting ? 'Opening…' : step.done ? 'Reconnect' : 'Connect LinkedIn'}
          </button>
        </div>
      )

    case 'publish':
      return (
        <div className={`${text} space-y-3`}>
          <p>
            On the app&rsquo;s <span className={strong}>Products</span> tab, add{' '}
            <span className={strong}>Share on LinkedIn</span> and{' '}
            <span className={strong}>Sign In with LinkedIn using OpenID Connect</span>.
          </p>
          <p>
            This is the one that catches people out. Without the first product, everything
            looks fine — you sign in, the account connects — and then every post fails,
            because the grant carries no permission to publish.
          </p>
          {step.detail && <p className="text-danger-soft">{step.detail}</p>}
          <p>
            Adding a product does not change a token you already hold. After adding it, use{' '}
            <span className={strong}>Reconnect</span> above.
          </p>
        </div>
      )

    default:
      return null
  }
}

export default function Setup() {
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['setup', 'state'],
    queryFn: getSetupState,
    // Work happens in another tab; polling is how this one finds out.
    refetchInterval: (q) => (q.state.data?.complete ? false : 4000),
    // Without this the polling stops whenever the tab loses focus — which is
    // precisely when it is needed, since the user is off in the LinkedIn tab
    // doing the thing being waited for. Measured: the step stayed unticked
    // indefinitely until the page was reloaded by hand.
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  })

  const handleConnect = async () => {
    setError(null)
    setConnecting(true)
    // Claimed synchronously — a popup blocker only allows window.open inside
    // the click, and the URL has to be fetched first.
    const tab = openBlankTab()
    try {
      const url = query.data?.steps.find((s) => s.id === 'connect')?.done
        ? await getLinkedInAuthorizeUrl()
        : linkedInLoginUrl()
      if (tab) tab.location.href = url
      else window.location.href = url
    } catch (err) {
      tab?.close()
      setError((err as Error).message)
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl animate-rise-in">
      <h1 className={H1}>Set up publishing</h1>
      <p className={SUB}>
        Four steps, mostly in LinkedIn&rsquo;s developer portal. Each one is checked here as
        you go — nothing to confirm by hand.
      </p>

      {query.isPending && <div className="mt-10"><QueryPending label="Checking setup…" /></div>}

      {query.isError && (
        <div className="mt-10">
          <QueryError title="Could not check setup" message={(query.error as Error).message} />
        </div>
      )}

      {query.isSuccess && (
        <>
          {query.data.complete && (
            <div className="mt-8 border border-violet-500/40 bg-violet-500/[0.08] px-5 py-4">
              <p className="text-[16px] text-violet-200">Everything is connected.</p>
              <p className="mt-1 text-[15px] text-mist-500">
                You can{' '}
                <Link to="/upload" className="text-violet-300 underline underline-offset-2">
                  upload a reel
                </Link>{' '}
                and publish it.
              </p>
            </div>
          )}

          <ol className="mt-8 space-y-3">
            {query.data.steps.map((step, i) => {
              // The first unfinished step is the one to act on; later ones are
              // dimmed so the page reads as a sequence rather than a checklist.
              const firstOpen = query.data.steps.findIndex((s) => !s.done)
              const isCurrent = i === firstOpen
              const isFuture = firstOpen !== -1 && i > firstOpen

              return (
                <li
                  key={step.id}
                  className={`surface p-5 transition ${
                    isCurrent ? 'border-violet-500/40' : ''
                  } ${isFuture ? 'opacity-55' : ''}`}
                >
                  <div className="flex gap-4">
                    <Tick done={step.done} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <h2 className={H2}>
                          {i + 1}. {step.title}
                        </h2>
                        {step.done && (
                          <span className="text-[13px] text-violet-300">Done</span>
                        )}
                      </div>

                      {(isCurrent || step.done) && (
                        <div className="mt-3">
                          <StepBody
                            step={step}
                            redirectUri={query.data.redirect_uri}
                            isAdmin={query.data.is_admin}
                            onConnect={() => void handleConnect()}
                            connecting={connecting}
                            hasOwnApp={query.data.has_own_linkedin_app}
                            ownClientId={query.data.own_linkedin_client_id}
                            onOwnAppChanged={() =>
                              void queryClient.invalidateQueries({ queryKey: ['setup', 'state'] })
                            }
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>

          {error && <p className="mt-4 text-[15px] text-danger-soft">{error}</p>}

          <p className="mt-8 text-[15px] text-mist-500">
            Stuck? The{' '}
            <Link to="/docs" className="text-violet-300 underline underline-offset-2">
              docs
            </Link>{' '}
            cover the same ground in more detail.
          </p>
        </>
      )}
    </div>
  )
}
