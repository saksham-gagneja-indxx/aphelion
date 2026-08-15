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
import BoltLogo from './BoltLogo'
import { linkedInLoginUrl, openBlankTab } from '../api/auth'
import { BANNER_DANGER, BTN_OUTLINE, BTN_PRIMARY, EYEBROW } from '../ui'

const MESSAGES: Record<string, { text: string; type: 'error' | 'info' }> = {
  denied: { text: 'You declined the LinkedIn authorization request. Please authorize to sign in.', type: 'error' },
  state_mismatch: { text: 'Security check failed (state mismatch). Please try signing in again.', type: 'error' },
  token_failed: { text: 'Failed to retrieve access token from LinkedIn.', type: 'error' },
  userinfo_failed: { text: 'Failed to fetch your profile from LinkedIn.', type: 'error' },
  network_error: { text: 'A network error occurred while communicating with LinkedIn.', type: 'error' },
  pending_approval: { text: 'Your account is awaiting approval.', type: 'info' },
}

const DOCS_URL = 'https://github.com/saksham-gagneja-indxx/social-media-manager#readme'

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
    },
    {
      pill: 'border-violet-500/50 bg-violet-900 text-violet-200',
      dot: 'bg-violet-500',
      status: 'Posted',
      caption: 'Behind the scenes: how the byte-range upload actually works',
      when: 'Mon, Aug 17 · 8:02 AM',
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
      <div className="surface border-b-0">
        {/* Browser chrome */}
        <div className="flex items-center gap-2.5 border-b border-line px-5 py-3.5">
          <span className="h-2 w-2 rounded-full bg-line" />
          <span className="h-2 w-2 rounded-full bg-line" />
          <span className="h-2 w-2 rounded-full bg-line" />
          <span className="ml-3 truncate text-[14px] text-mist-500">
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
            <div key={s.label} className="bg-ink-900 px-6 py-6">
              <div className={EYEBROW}>{s.label}</div>
              <div className="mt-3 font-display text-[32px] font-light tracking-[-.02em] text-mist-50">
                {s.value}
              </div>
            </div>
          ))}
        </div>

        {/* Condensed post rows */}
        <div className="flex flex-col gap-px bg-line">
          {rows.map((r) => (
            <div key={r.status} className="flex items-center gap-4 bg-ink-900 px-5 py-4">
              <div className="h-12 w-9 shrink-0 border border-line bg-ink-800" />
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
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-y-4 px-8 py-5">
          <div className="flex items-center gap-2.5">
            <BoltLogo width={20} height={19} className="text-violet-500" />
            <span className="font-display text-[17px] font-medium tracking-[-.01em] text-mist-50">
              Reel Automation
            </span>
          </div>
          <div className="hidden items-center gap-8 sm:flex">
            <a href="#product" className="text-[16px] text-mist-500 hover:text-mist-50">
              Product
            </a>
            <a
              href={DOCS_URL}
              target="_blank"
              rel="noreferrer"
              className="text-[16px] text-mist-500 hover:text-mist-50"
            >
              Docs
            </a>
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

      <div className="relative z-10 mx-auto flex max-w-[1280px] flex-col items-center px-8 pt-20">
        {/* Status chip */}
        <div className="animate-rise flex max-w-full flex-wrap items-center justify-center gap-3 border border-line bg-ink-900 py-1.5 pr-4 pl-1.5">
          <span className={`${EYEBROW} inline-flex items-center gap-2 bg-violet-900 px-2.5 py-1 text-violet-200`}>
            <span className="animate-blink h-1.5 w-1.5 rounded-full bg-violet-300" />
            Live
          </span>
          <span className="text-[15px] text-mist-200">
            LinkedIn publishing shipped via the official REST API
          </span>
        </div>

        <h1 className="animate-rise mt-8 max-w-[900px] text-center font-display text-[40px] leading-[1.0] font-light tracking-[-.03em] text-balance text-mist-50 [animation-delay:.1s] sm:text-[60px] lg:text-[80px]">
          Schedule once.
          <br />
          Ship <span className="text-violet-500">every reel</span> on time.
        </h1>

        <p className="animate-rise mt-8 max-w-[620px] text-center text-[18px] leading-[1.6] text-pretty text-mist-200 [animation-delay:.2s]">
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

        {/* Both CTAs start the same OAuth flow — there is no separate signup. */}
        <div className="animate-rise mt-10 flex w-full flex-wrap items-center justify-center gap-3 [animation-delay:.3s]">
          <button
            type="button"
            onClick={startSignIn}
            className={`${BTN_PRIMARY} px-8 py-4 text-[18px]`}
          >
            Start for free
            <svg
              className="h-5 w-5"
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
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className={`${BTN_OUTLINE} px-8 py-4 text-[18px] hover:text-mist-50`}
          >
            Read the docs
          </a>
        </div>

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
