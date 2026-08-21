/**
 * Landing page for the website-mediated MCP connector authorization.
 *
 * Reached when someone clicks "Connect" on the Aphelion connector in
 * Claude: the Cloudflare Worker's own OAuth flow sends the browser here
 * instead of to GitHub (or any third-party consent screen) - see
 * mcp-server/src/site-handler.ts. This page is what actually authenticates
 * them, using whatever this deployment already uses (Clerk, or plain
 * LinkedIn sign-in), then hands a short-lived grant back to the Worker so it
 * can finish its own handshake with Claude and bounce the browser back.
 *
 * Query params (set by the Worker):
 *   state      - the Worker's own OAuth state, opaque to us
 *   return_to  - the Worker's callback URL to redirect to once approved
 *
 * Deliberately outside the authenticated app shell (see App.tsx routing it
 * before the /api/me check) - a fresh visitor reaching this page has no
 * session yet, and the whole point is to get them one without detouring
 * through the normal dashboard.
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { SignInButton } from '@clerk/clerk-react'
import BoltLogo from '../components/BoltLogo'
import { ClerkSessionBridge } from '../components/Landing'
import {
  authorizeMcpConnector,
  CLERK_ENABLED,
  CLERK_SIGNIN_ENABLED,
  getLinkedInAuthorizeUrl,
  getMe,
  linkedInLoginUrl,
} from '../api/auth'
import { BTN_PRIMARY, META } from '../ui'

function currentPathWithQuery(): string {
  return window.location.pathname + window.location.search
}

export default function McpAuthorize() {
  const params = new URLSearchParams(window.location.search)
  const workerState = params.get('state') ?? ''
  const returnTo = params.get('return_to') ?? ''

  const { data: user, isPending, isError, error: meError } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    retry: false,
  })

  const [connectingLinkedIn, setConnectingLinkedIn] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const missingParams = !workerState || !returnTo
  // Signed in, but not yet approved (see backend's is_active gate) - distinct
  // from "not signed in at all": showing a sign-in button here would be
  // wrong, they already did that part.
  const pendingApproval = isError && meError?.message === 'Forbidden'
  const signedIn = !isPending && !isError && !!user
  const linkedInConnected = signedIn && user.linkedin_connected

  // Once signed in AND LinkedIn-connected, finish automatically - no extra
  // click needed for the common case (an existing, already-connected account).
  useEffect(() => {
    if (missingParams || !linkedInConnected || finishing) return
    let cancelled = false
    setFinishing(true)
    setError(null)
    void (async () => {
      try {
        const grant = await authorizeMcpConnector(workerState)
        if (cancelled) return
        const url = new URL(returnTo)
        url.searchParams.set('state', workerState)
        url.searchParams.set('grant', grant)
        window.location.href = url.toString()
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message)
          setFinishing(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-run only when these actually change
  }, [missingParams, linkedInConnected, workerState, returnTo])

  async function connectLinkedIn() {
    setConnectingLinkedIn(true)
    setError(null)
    try {
      const url = await getLinkedInAuthorizeUrl(currentPathWithQuery())
      window.location.href = url
    } catch (err) {
      setError((err as Error).message)
      setConnectingLinkedIn(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-ink-950 px-6 text-center">
      <BoltLogo className="mb-8 h-8 w-8 text-mist-50" />
      <h1 className="font-display text-[32px] font-light tracking-[-.02em] text-mist-50">
        Connect Aphelion
      </h1>
      <p className="mt-3 max-w-[420px] text-[15px] leading-[1.65] text-mist-500">
        Claude wants to connect to your Aphelion account.
      </p>

      {missingParams ? (
        <p className={`${BANNER_DANGER_INLINE} mt-6 max-w-[420px]`}>
          This link is missing required information - go back to Claude and try connecting again.
        </p>
      ) : (
        <div className="mt-8 flex w-full max-w-[360px] flex-col items-center gap-3">
          {isPending ? (
            <p className={META}>Checking your account…</p>
          ) : pendingApproval ? (
            <p className={META}>
              You're signed in, but this account still needs the owner's approval before it can
              connect. Check back with them, then try connecting from Claude again.
            </p>
          ) : !signedIn ? (
            CLERK_ENABLED && CLERK_SIGNIN_ENABLED ? (
              <>
                <SignInButton mode="modal">
                  <button type="button" className={`${BTN_PRIMARY} w-full justify-center`}>
                    Sign in to continue
                  </button>
                </SignInButton>
                <ClerkSessionBridge />
              </>
            ) : (
              <a
                href={`${linkedInLoginUrl()}?next=${encodeURIComponent(currentPathWithQuery())}`}
                className={`${BTN_PRIMARY} w-full justify-center`}
              >
                Sign in with LinkedIn
              </a>
            )
          ) : !linkedInConnected ? (
            <>
              <p className={`${META} text-center`}>
                Signed in as {user.name || user.email}. Aphelion also needs LinkedIn connected to
                publish on your behalf.
              </p>
              <button
                type="button"
                onClick={() => void connectLinkedIn()}
                disabled={connectingLinkedIn}
                className={`${BTN_PRIMARY} w-full justify-center`}
              >
                {connectingLinkedIn ? 'Opening LinkedIn…' : 'Connect LinkedIn'}
              </button>
            </>
          ) : (
            <p className={META}>Connecting Aphelion to Claude…</p>
          )}

          {error && <p className={`${BANNER_DANGER_INLINE} w-full`}>{error}</p>}
        </div>
      )}
    </div>
  )
}

const BANNER_DANGER_INLINE = 'border border-danger/40 bg-danger/[0.07] px-4 py-3 text-[14px] text-danger-soft'
