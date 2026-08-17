/**
 * Signed-out landing page.
 *
 * This is also the sign-in gate: App renders it whenever /api/me answers 401.
 * Clerk is the ONLY way in - one "Sign in" trigger, everywhere on this page,
 * always opening the same modal. Clerk's own "Don't have an account? Sign up"
 * link inside that modal covers sign-up, so there is deliberately no separate
 * sign-up button here to keep in sync with it.
 *
 * LinkedIn is reachable as one of Clerk's OAuth providers in that same modal -
 * there is no second, direct-to-LinkedIn button. That direct button used to
 * call this SERVER's own LinkedIn app straight from the landing page (bypassing
 * Clerk, and identity, entirely) purely to sign in; the identity question is
 * Clerk's job now. The server's own LinkedIn app is still used, unchanged, for
 * the thing only it can do: granting w_member_social publish rights, which
 * happens later in Setup once the visitor is already a recognised, signed-in
 * account - see backend/api/auth_routes.py's /auth/linkedin/start.
 *
 * Styled to render.com's structure — 80px/300 display type, square edges,
 * hairline rules, a white primary button — with violet as the only accent.
 *
 * Two departures from the source design:
 *   - The nav carries only links that resolve. Platforms / Changelog / System
 *     have no page behind them yet, so they are not rendered.
 *   - The spec row states the limits the app actually enforces (see
 *     api/validation.ts), not the marketing copy's "MP4 only · 3s – 30 min".
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { SignInButton, useAuth } from '@clerk/clerk-react'
import BoltLogo from './BoltLogo'
import { CLERK_ENABLED, bridgeClerkSession, getGuestEnabled, signInAsGuest } from '../api/auth'
import { BANNER_DANGER, BTN_OUTLINE, BTN_PRIMARY, EYEBROW, META } from '../ui'

/** The in-app docs, not the GitHub README: a visitor here has no repository
 *  access, and the page they need explains how to get an account. */
const DOCS_PATH = '/docs'

/**
 * Hairline grid with a single violet wash behind the headline. Static: the
 * system has no drifting gradients, and one soft light source is all the
 * depth a flat black page needs.
 */
function HeroBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(#272727 1px, transparent 1px), linear-gradient(90deg, #272727 1px, transparent 1px)',
          backgroundSize: '72px 72px',
          maskImage: 'radial-gradient(120% 80% at 50% 0%, #000 20%, transparent 75%)',
          WebkitMaskImage: 'radial-gradient(120% 80% at 50% 0%, #000 20%, transparent 75%)',
        }}
      />
      <div
        className="absolute -top-[280px] left-1/2 h-[620px] w-[1100px] -translate-x-1/2"
        style={{
          background: 'radial-gradient(closest-side, rgba(138,5,255,.30), transparent)',
        }}
      />
    </div>
  )
}

/**
 * Stylised preview of the Queue screen. Decorative — the figures are
 * illustrative, not this account's, so it stays out of the a11y tree.
 */
function ProductPreview() {
  const stats = [
    { label: 'Scheduled', value: '12' },
    { label: 'Posted this week', value: '37' },
    { label: 'Peak hour', value: '09:00' },
  ]
  const rows = [
    {
      pill: 'border-violet-500/45 bg-violet-500/[0.12] text-violet-300',
      dot: 'bg-violet-500',
      status: 'Scheduled',
      caption: 'Three things I learned shipping an OAuth integration in a week',
      when: 'Tue, Aug 18 · 9:00 AM',
      icon: 'linkedin',
    },
    {
      pill: 'border-violet-500/50 bg-violet-900 text-violet-200',
      dot: 'bg-violet-500',
      status: 'Posted',
      caption: 'Behind the scenes: how the byte-range upload actually works',
      when: 'Mon, Aug 17 · 8:02 AM',
      icon: 'instagram',
    },
  ]

  return (
    <div
      id="product"
      aria-hidden="true"
      /* min-w-0: without it this block's min-content width (three stat
         columns plus a row of nowrap timestamps) widens the centred column
         past the viewport and drags the whole hero off-screen on phones. */
      className="animate-rise relative mx-auto mt-16 -mb-px w-full max-w-[1060px] min-w-0 scroll-mt-24 [animation-delay:.5s]"
    >
      <div className="surface border-b-0 rounded-2xl">
        {/* Browser chrome */}
        <div className="flex items-center gap-2.5 border-b border-line px-5 py-3.5">
          <span className="h-2 w-2 shrink-0 rounded-full bg-red-500" />
          <span className="h-2 w-2 shrink-0 rounded-full bg-green-500" />
          <span className="h-2 w-2 shrink-0 rounded-full bg-white" />
          <span className="ml-1 sm:ml-3 min-w-0 flex-1 truncate text-[14px] text-mist-500">
            app.reelautomation.io / queue
          </span>
          <span className="ml-auto hidden shrink-0 items-center gap-2 text-[14px] text-mist-200 sm:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-violet-500" />
            {' '}LinkedIn connected
          </span>
        </div>

        {/* Stat strip — 1px gaps let the hairline colour show through */}
        <div className="grid grid-cols-3 gap-px bg-line">
          {stats.map((s) => (
            <div key={s.label} className="bg-ink-900 px-3 py-4 sm:px-6 sm:py-6 text-center sm:text-left">
              <div className={EYEBROW}>{s.label}</div>
              <div className="mt-2 sm:mt-3 font-display text-[24px] sm:text-[32px] font-light tracking-[-.02em] text-mist-50">
                {s.value}
              </div>
            </div>
          ))}
        </div>

        {/* Condensed post rows */}
        <div className="flex flex-col gap-px bg-line">
          {rows.map((r) => (
            <div key={r.status} className="flex items-center gap-4 bg-ink-900 px-5 py-4">
              <div className="flex h-12 w-9 shrink-0 items-center justify-center border border-line bg-ink-800">
                {r.icon === 'linkedin' ? (
                  <svg className="h-4 w-4 text-mist-500" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                  </svg>
                ) : (
                  <svg className="h-4 w-4 text-mist-500" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                  </svg>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <span
                  className={`inline-flex items-center gap-2 border px-2.5 py-0.5 text-[13px] ${r.pill}`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${r.dot}`} />
                  {r.status}
                </span>
                <p className="mt-2 truncate text-[15px] text-mist-200">{r.caption}</p>
              </div>
              <span className="hidden shrink-0 text-[14px] whitespace-nowrap text-mist-500 sm:inline">
                {r.when}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * Bridges a Clerk sign-in into this app's own session, silently.
 *
 * Only ever mounted when CLERK_ENABLED (see the render below), so calling
 * Clerk's hooks here unconditionally is safe - this component simply does not
 * exist in a deployment that hasn't configured Clerk.
 *
 * Runs once Clerk reports the visitor as signed in: fetches a Clerk session
 * token, trades it for this app's own token (bridgeClerkSession), and
 * invalidates the ['me'] query so App swaps the landing page for the app
 * without a manual reload - the same pattern the guest button uses.
 */
function ClerkSessionBridge() {
  const { isSignedIn, isLoaded, getToken } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [bridging, setBridging] = useState(false)

  useEffect(() => {
    if (!isLoaded || !isSignedIn || bridging) return

    let cancelled = false
    setBridging(true)
    setError(null)
    void (async () => {
      try {
        const clerkToken = await getToken()
        if (!clerkToken) throw new Error('Clerk did not return a session token.')
        await bridgeClerkSession(clerkToken)
        if (!cancelled) {
          await queryClient.invalidateQueries({ queryKey: ['me'] })
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      } finally {
        if (!cancelled) setBridging(false)
      }
    })()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-run only on sign-in state changes
  }, [isLoaded, isSignedIn])

  if (!isSignedIn) return null

  return (
    <div className="mt-4 w-full max-w-[560px] text-center text-[14px] text-mist-500">
      {error ? (
        <p className={`${BANNER_DANGER} text-danger-soft`}>
          Could not finish signing you in: {error}
        </p>
      ) : (
        <p>Finishing sign-in…</p>
      )}
    </div>
  )
}

export default function Landing() {
  const [guestBusy, setGuestBusy] = useState(false)
  const [guestError, setGuestError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  // Only offered when the server actually allows it, so a deployment with
  // guests turned off does not show a button that always fails.
  const { data: guestEnabled } = useQuery({
    queryKey: ['guest', 'enabled'],
    queryFn: getGuestEnabled,
    staleTime: 60_000,
  })

  const startGuest = async () => {
    setGuestError(null)
    setGuestBusy(true)
    try {
      await signInAsGuest()
      // The token is in place; re-running the identity check swaps the landing
      // page for the app without a reload.
      await queryClient.invalidateQueries({ queryKey: ['me'] })
    } catch (err) {
      setGuestError((err as Error).message)
      setGuestBusy(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-ink-950">
      <HeroBackdrop />

      <nav className="relative z-10 border-b border-line">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-y-4 px-4 sm:px-8 py-5">
          <div aria-label="Reel Automation">
            <BoltLogo width={44} height={40} className="text-mist-50" />
          </div>
          <div className="hidden items-center gap-8 pl-[130px] sm:flex">
            <a href="#product" className="text-[16px] text-mist-500 hover:text-mist-50">
              Product
            </a>
            <Link to={DOCS_PATH} className="text-[16px] text-mist-500 hover:text-mist-50">
              Docs
            </Link>
          </div>
          <div className="flex items-center gap-3 scale-[0.8] origin-right">
            {CLERK_ENABLED ? (
              <SignInButton mode="modal">
                <button type="button" className={BTN_PRIMARY}>
                  Sign in
                </button>
              </SignInButton>
            ) : (
              <span className={META}>Sign-in is not configured on this server.</span>
            )}
          </div>
        </div>
      </nav>

      <div className="relative z-10 mx-auto flex max-w-[1280px] flex-col items-center px-4 sm:px-8 pt-4">
        {/* Status chip */}
        <div className="animate-rise flex max-w-full flex-wrap items-center justify-center gap-3 rounded-lg py-1.5 pr-4 pl-1.5">
          <span className={`${EYEBROW} inline-flex items-center gap-2 bg-violet-900 px-2.5 py-1 text-violet-200 rounded-lg`}>
            <span className="animate-blink h-1.5 w-1.5 rounded-full bg-white" />
            {' '}Live
          </span>
          <span className="text-[15px] text-mist-200">
            With Integrated Linkedin OAuth Channels
        </span>
        </div>

        <h1 className="animate-rise mt-8 max-w-[900px] text-center font-display text-[40px] leading-[1.0] font-light tracking-[-.03em] text-balance text-mist-50 [animation-delay:.1s] sm:text-[60px] lg:text-[80px]">
          Schedule once.
          <br />
          Ship <span className="text-violet-500">every reel</span> on time.
        </h1>

        <p className="animate-rise mt-8 max-w-[620px] text-center text-[16px] leading-[1.6] text-pretty text-mist-200/80 [animation-delay:.2s]">
          Drop in a reel, pick a time, walk away. We validate the file, pull a thumbnail, and
          publish through LinkedIn&rsquo;s official API — with a queue that tells you exactly what
          happened, and why.
        </p>

        {/* One sign-in trigger, one place it lives. Clerk's own modal covers
            sign-up ("Don't have an account?") and every OAuth provider,
            LinkedIn included - there is nothing else to wire up here. Guest
            is unrelated to identity: a real, sandboxed account for trying the
            tool without any provider at all. */}
        <div className="animate-rise mt-10 flex w-full max-w-[560px] flex-col items-center justify-center gap-3 [animation-delay:.3s] scale-90">
          <div className="flex w-full flex-row items-center justify-center gap-3">
            {CLERK_ENABLED ? (
              <SignInButton mode="modal">
                <button
                  type="button"
                  className={`${BTN_PRIMARY} flex-1 justify-center px-[13px] sm:px-[18px] py-3 sm:py-4 text-[13px] sm:text-[18px] whitespace-nowrap`}
                >
                  Sign in
                </button>
              </SignInButton>
            ) : (
              <p className={`${META} flex-1 text-center`}>Sign-in is not configured on this server.</p>
            )}
            {guestEnabled && (
              <button
                type="button"
                onClick={() => void startGuest()}
                disabled={guestBusy}
                className={`${BTN_OUTLINE} flex-1 justify-center px-[13px] sm:px-[18px] py-3 sm:py-4 text-[13px] sm:text-[18px] hover:text-mist-50 whitespace-nowrap`}
              >
                {guestBusy ? 'Setting up…' : 'Try as a guest'}
              </button>
            )}
          </div>
          {CLERK_ENABLED && <ClerkSessionBridge />}
          <Link
            to={DOCS_PATH}
            className={`${BTN_OUTLINE} w-full justify-center px-8 py-3 sm:py-4 text-[13px] sm:text-[18px] hover:text-mist-50`}
          >
            Read the docs
          </Link>
        </div>

        {guestEnabled && (
          <p className="animate-fade-in mt-5 max-w-[520px] text-center text-[15px] text-mist-500 [animation-delay:.35s]">
            A guest account lets you upload, caption and schedule. Publishing needs
            LinkedIn, since that posts to a real profile.
          </p>
        )}
        {guestError && (
          <p className="mt-4 text-[15px] text-danger-soft">{guestError}</p>
        )}

        {/* Kept in step with api/validation.ts — these are the limits enforced. */}
        <div className={`${EYEBROW} animate-fade-in mt-10 flex w-full flex-wrap items-center justify-center gap-x-6 gap-y-2 text-center [animation-delay:.4s]`}>
          <span>MP4, MOV, AVI, MKV or WEBM</span>
          <span className="text-line">/</span>
          <span>up to 90 seconds</span>
          <span className="text-line">/</span>
          <span>up to 500 MB</span>
          <span className="text-line">/</span>
          <span>OAuth only, no passwords</span>
        </div>

        <ProductPreview />
      </div>
    </div>
  )
}
