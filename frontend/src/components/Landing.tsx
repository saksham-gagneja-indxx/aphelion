/**
 * Signed-out landing page.
 *
 * This is also the sign-in gate: App renders it whenever /api/me answers 401,
 * so every call to action starts the LinkedIn OAuth flow, and the
 * ?linkedin=<status> messages the callback redirects with surface here.
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
import BoltLogo from './BoltLogo'
import { getGuestEnabled, linkedInLoginUrl, openBlankTab, signInAsGuest } from '../api/auth'
import { BANNER_DANGER, BTN_OUTLINE, BTN_PRIMARY, EYEBROW } from '../ui'

const MESSAGES: Record<string, { text: string; type: 'error' | 'info' }> = {
  denied: { text: 'You declined the LinkedIn authorization request. Please authorize to sign in.', type: 'error' },
  state_mismatch: { text: 'Security check failed (state mismatch). Please try signing in again.', type: 'error' },
  token_failed: { text: 'Failed to retrieve access token from LinkedIn.', type: 'error' },
  userinfo_failed: { text: 'Failed to fetch your profile from LinkedIn.', type: 'error' },
  network_error: { text: 'A network error occurred while communicating with LinkedIn.', type: 'error' },
  pending_approval: { text: 'Your account is awaiting approval.', type: 'info' },
}

/** The in-app docs, not the GitHub README: a visitor here has no repository
 *  access, and the page they need explains how to get an account. */
const DOCS_PATH = '/docs'

/**
 * Consent happens in a new tab, so this page (and anything typed into it) is
 * still here afterwards. The tab closes itself once it has the token, and this
 * one refreshes off the resulting 'storage' event - see App.
 *
 * linkedInLoginUrl() carries API_BASE: empty on a same-origin deploy, set when
 * frontend and backend live on different hosts (Vercel + Render). A bare path
 * would send the browser to the frontend's own origin and 404.
 *
 * Falls back to navigating this tab when a popup blocker refuses the open,
 * which is the old behaviour rather than a dead button.
 */
const startSignIn = () => {
  const tab = openBlankTab()
  if (tab) {
    tab.location.href = linkedInLoginUrl()
  } else {
    window.location.href = linkedInLoginUrl()
  }
}

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
            LinkedIn connected
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

export default function Landing() {
  const [msg, setMsg] = useState<{ text: string; type: 'error' | 'info' } | null>(null)
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

  useEffect(() => {
    // Parse query params for ?linkedin=<status>
    const params = new URLSearchParams(window.location.search)
    const status = params.get('linkedin')
    if (status && status !== 'connected') {
      setMsg(MESSAGES[status] || { text: `Authentication failed: ${status}`, type: 'error' })
      // Optionally remove the query param so a refresh doesn't keep showing it
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [])

  return (
    <div className="relative min-h-screen overflow-hidden bg-ink-950">
      <HeroBackdrop />

      <nav className="relative z-10 border-b border-line">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-y-4 px-4 sm:px-8 py-5">
          <div aria-label="Reel Automation">
            <BoltLogo width={44} height={40} className="text-mist-50" />
          </div>
          <div className="hidden items-center gap-8 sm:flex">
            <a href="#product" className="text-[16px] text-mist-500 hover:text-mist-50">
              Product
            </a>
            <Link to={DOCS_PATH} className="text-[16px] text-mist-500 hover:text-mist-50">
              Docs
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={startSignIn} className={BTN_OUTLINE}>
              Sign in
            </button>
            <button type="button" onClick={startSignIn} className={BTN_PRIMARY}>
              Start for free
            </button>
          </div>
        </div>
      </nav>

      <div className="relative z-10 mx-auto flex max-w-[1280px] flex-col items-center px-4 sm:px-8 pt-20">
        {/* Status chip */}
        <div className="animate-rise flex max-w-full flex-wrap items-center justify-center gap-3 rounded-lg py-1.5 pr-4 pl-1.5">
          <span className={`${EYEBROW} inline-flex items-center gap-2 bg-violet-900 px-2.5 py-1 text-violet-200 rounded-lg`}>
            <span className="animate-blink h-1.5 w-1.5 rounded-full bg-white" />
            Live
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

        <p className="animate-rise mt-8 max-w-[620px] text-center text-[16px] leading-[1.6] text-pretty text-mist-200 [animation-delay:.2s]">
          Drop in a reel, pick a time, walk away. We validate the file, pull a thumbnail, and
          publish through LinkedIn&rsquo;s official API — with a queue that tells you exactly what
          happened, and why.
        </p>

        {msg && (
          <div
            className={`mt-8 w-full max-w-[620px] text-left text-[15px] ${
              msg.type === 'error'
                ? `${BANNER_DANGER} text-danger-soft`
                : 'border border-line bg-ink-900 px-4 py-3.5 text-mist-200'
            }`}
          >
            {msg.text}
          </div>
        )}

        {/* Sign in starts OAuth — there is no separate signup. Guest is a real
            account, just a sandboxed one; see the note under the buttons. */}
        <div className="animate-rise mt-10 flex w-full max-w-[560px] flex-col items-center justify-center gap-3 [animation-delay:.3s] scale-90">
          <div className="flex w-full flex-row items-center justify-center gap-3">
            <button
              type="button"
              onClick={startSignIn}
              className={`${BTN_PRIMARY} flex-1 justify-center px-[13px] sm:px-[18px] py-3 sm:py-4 text-[13px] sm:text-[18px] whitespace-nowrap`}
            >
              Sign in with LinkedIn
              <svg
                className="h-4 w-4 sm:h-5 sm:w-5 shrink-0"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14m-6-6 6 6-6 6" />
              </svg>
            </button>
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
