/**
 * Signed-out landing page — frame 1a of the Dark Glass v1 handoff.
 *
 * This is also the sign-in gate: App renders it whenever /api/me answers 401,
 * so every call to action starts the LinkedIn OAuth flow, and the
 * ?linkedin=<status> messages the callback redirects with surface here.
 *
 * Two departures from the prototype, both deliberate:
 *   - The nav carries only links that resolve. Platforms / Changelog / System
 *     have no page behind them yet, so they are not rendered.
 *   - The spec row states the limits the app actually enforces (see
 *     api/validation.ts), not the prototype's "MP4 only · 3s – 30 min".
 */
import { useEffect, useState } from 'react'
import BoltLogo from './BoltLogo'

const MESSAGES: Record<string, { text: string; type: 'error' | 'info' }> = {
  denied: { text: 'You declined the LinkedIn authorization request. Please authorize to sign in.', type: 'error' },
  state_mismatch: { text: 'Security check failed (state mismatch). Please try signing in again.', type: 'error' },
  token_failed: { text: 'Failed to retrieve access token from LinkedIn.', type: 'error' },
  userinfo_failed: { text: 'Failed to fetch your profile from LinkedIn.', type: 'error' },
  network_error: { text: 'A network error occurred while communicating with LinkedIn.', type: 'error' },
  pending_approval: { text: 'Your account is awaiting approval.', type: 'info' },
}

const DOCS_URL = 'https://github.com/saksham-gagneja-indxx/social-media-manager#readme'

const startSignIn = () => {
  window.location.href = '/api/auth/linkedin/login'
}

/** Aurora blobs, masked grid, and the fade that lands the section on ink-900. */
function HeroBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="animate-drift-a absolute -top-[260px] left-[44%] h-[620px] w-[820px] rounded-full blur-[30px]"
        style={{ background: 'radial-gradient(closest-side, rgba(134,59,255,.55), rgba(134,59,255,0))' }}
      />
      <div
        className="animate-drift-b absolute -top-[180px] left-[6%] h-[520px] w-[640px] rounded-full blur-[30px]"
        style={{ background: 'radial-gradient(closest-side, rgba(170,59,255,.34), rgba(170,59,255,0))' }}
      />
      <div
        className="animate-drift-c absolute top-[180px] -right-[140px] h-[560px] w-[560px] rounded-full blur-[40px]"
        style={{ background: 'radial-gradient(closest-side, rgba(83,26,190,.42), rgba(83,26,190,0))' }}
      />
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(237,230,255,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(237,230,255,.045) 1px, transparent 1px)',
          backgroundSize: '72px 72px',
          maskImage: 'radial-gradient(120% 80% at 50% 0%, #000 25%, transparent 78%)',
          WebkitMaskImage: 'radial-gradient(120% 80% at 50% 0%, #000 25%, transparent 78%)',
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          background:
            'linear-gradient(180deg, rgba(8,6,13,0) 40%, rgba(8,6,13,.86) 88%, #08060D 100%)',
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
      tint: 'linear-gradient(150deg, rgba(170,59,255,.4), rgba(134,59,255,.12))',
      pill: 'border-status-scheduled/30 bg-status-scheduled/[0.16] text-lilac-300',
      dot: 'bg-status-scheduled',
      status: 'Scheduled',
      caption: 'Three things I learned shipping an OAuth integration in a week',
      when: 'Tue, Aug 18 · 9:00 AM',
    },
    {
      tint: 'linear-gradient(150deg, rgba(52,211,153,.3), rgba(134,59,255,.1))',
      pill: 'border-status-posted/30 bg-status-posted/[0.14] text-[#6EE7B7]',
      dot: 'bg-status-posted',
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
      className="animate-rise-slow relative mx-auto mt-[62px] -mb-px w-full max-w-[1060px] min-w-0 scroll-mt-24 [animation-delay:.6s]"
    >
      <div
        className="pointer-events-none absolute -inset-x-5 -top-10 bottom-10 blur-[20px]"
        style={{
          background: 'radial-gradient(60% 60% at 50% 0%, rgba(134,59,255,.35), transparent 70%)',
        }}
      />
      <div className="glass-overlay relative overflow-hidden rounded-t-[20px] border-b-0 shadow-[inset_0_1px_0_rgba(237,230,255,.14),0_40px_90px_rgba(0,0,0,.55)]">
        {/* Browser chrome */}
        <div className="flex items-center gap-2.5 border-b border-lilac-50/[0.09] bg-ink-900/40 px-[18px] py-3.5">
          <span className="h-[9px] w-[9px] rounded-full bg-lilac-50/[0.16]" />
          <span className="h-[9px] w-[9px] rounded-full bg-lilac-50/[0.16]" />
          <span className="h-[9px] w-[9px] rounded-full bg-lilac-50/[0.16]" />
          <span className="ml-3 truncate text-xs tracking-[.02em] text-lilac-50/42">
            app.reelautomation.io / queue
          </span>
          <span className="ml-auto hidden shrink-0 items-center gap-1.5 text-[11px] font-semibold tracking-[.08em] uppercase text-[#6EE7B7] sm:inline-flex">
            <span className="h-[5px] w-[5px] rounded-full bg-status-posted" />
            LinkedIn connected
          </span>
        </div>

        {/* Stat strip — 1px gaps show the container through as hairlines */}
        <div className="grid grid-cols-3 gap-px bg-lilac-50/[0.07]">
          {stats.map((s) => (
            <div key={s.label} className="bg-ink-900/55 px-[22px] py-5">
              <div className="text-[11px] font-semibold tracking-[.12em] uppercase text-lilac-50/38">
                {s.label}
              </div>
              <div className="mt-2 font-display text-[30px] font-bold tracking-[-.03em] text-lilac-50">
                {s.value}
              </div>
            </div>
          ))}
        </div>

        {/* Condensed post rows */}
        <div className="flex flex-col gap-2.5 bg-ink-900/35 p-[18px]">
          {rows.map((r) => (
            <div
              key={r.status}
              className="flex items-center gap-3.5 rounded-xl border border-lilac-50/[0.08] bg-lilac-50/[0.04] px-3.5 py-3"
            >
              <div
                className="h-12 w-[34px] shrink-0 rounded-[7px] border border-lilac-50/10"
                style={{ background: r.tint }}
              />
              <div className="min-w-0 flex-1">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-pill border px-[9px] py-0.5 text-[11px] font-semibold ${r.pill}`}
                >
                  <span className={`h-[5px] w-[5px] rounded-full ${r.dot}`} />
                  {r.status}
                </span>
                <p className="mt-[7px] truncate text-[13px] text-lilac-50/78">{r.caption}</p>
              </div>
              <span className="hidden shrink-0 text-xs whitespace-nowrap text-lilac-50/40 sm:inline">
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
    <div className="relative min-h-screen overflow-hidden bg-ink-900">
      <HeroBackdrop />

      <nav className="relative z-10 mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-y-4 px-8 py-5">
        <div className="flex items-center gap-2.5">
          <BoltLogo width={24} height={23} glow={12} />
          <span className="font-display text-[15px] font-bold tracking-[-.01em] text-lilac-50">
            Reel Automation
          </span>
        </div>
        <div className="hidden items-center gap-8 sm:flex">
          <a href="#product" className="text-sm font-medium text-lilac-50/72 hover:text-lilac-50">
            Product
          </a>
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-lilac-50/72 hover:text-lilac-50"
          >
            Docs
          </a>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={startSignIn}
            className="rounded-pill border border-lilac-50/[0.14] bg-lilac-50/[0.07] px-[18px] py-[9px] text-sm font-semibold text-lilac-50 backdrop-blur-[12px] transition hover:bg-lilac-50/[0.13]"
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={startSignIn}
            className="rounded-pill bg-[linear-gradient(180deg,#AA3BFF,#7E14FF)] px-5 py-2.5 text-sm font-semibold text-white shadow-glow transition hover:-translate-y-px hover:brightness-110"
          >
            Start for free
          </button>
        </div>
      </nav>

      <div className="relative z-10 mx-auto flex max-w-[1280px] flex-col items-center px-8 pt-16">
        {/* Status chip */}
        <div className="animate-rise inline-flex max-w-full flex-wrap items-center justify-center gap-2.5 rounded-[20px] border border-lilac-50/[0.12] bg-lilac-50/5 py-1.5 pr-2 pl-1.5 backdrop-blur-[14px] sm:rounded-pill">
          <span className="inline-flex items-center gap-1.5 rounded-pill border border-status-posted/30 bg-status-posted/[0.14] px-[9px] py-[3px] text-[11px] font-semibold tracking-[.08em] uppercase text-[#6EE7B7]">
            <span className="animate-blink h-[5px] w-[5px] rounded-full bg-status-posted" />
            Live
          </span>
          <span className="pr-2 text-[13px] text-lilac-50/70">
            LinkedIn publishing shipped via the official REST API
          </span>
        </div>

        <h1 className="animate-rise mt-[26px] max-w-[840px] text-center font-display text-[32px] leading-[1.03] font-bold tracking-[-.035em] text-balance text-lilac-50 [animation-delay:.12s] sm:text-[54px] lg:text-[66px]">
          Schedule once.
          <br />
          Ship{' '}
          <span className="bg-[linear-gradient(100deg,#EDE6FF_10%,#C9A9FF_40%,#AA3BFF_78%)] bg-clip-text text-transparent">
            every reel
          </span>{' '}
          on time.
        </h1>

        <p className="animate-rise mt-6 max-w-[600px] text-center text-[17px] leading-[1.65] text-pretty text-lilac-50/62 [animation-delay:.24s]">
          Drop in a reel, pick a time, walk away. We validate the file, pull a thumbnail, and
          publish through LinkedIn&rsquo;s official API — with a queue that tells you exactly what
          happened, and why.
        </p>

        {msg && (
          <div
            className={`mt-7 w-full max-w-[600px] rounded-xl border p-4 text-left text-[13.5px] ${
              msg.type === 'error'
                ? 'border-status-failed/[0.26] bg-status-failed/[0.09] text-[#FDA4AF]'
                : 'border-status-queued/[0.26] bg-status-queued/[0.09] text-[#93C5FD]'
            }`}
          >
            {msg.text}
          </div>
        )}

        {/* Both CTAs start the same OAuth flow — there is no separate signup. */}
        <div className="animate-rise mt-[34px] flex w-full flex-wrap items-center justify-center gap-3.5 [animation-delay:.36s]">
          <button
            type="button"
            onClick={startSignIn}
            className="animate-glow-pulse inline-flex min-w-[216px] items-center justify-between gap-7 rounded-pill bg-[linear-gradient(180deg,#AA3BFF,#7E14FF)] py-4 pr-5 pl-6 text-[15px] font-semibold text-white transition hover:scale-[1.03] hover:brightness-110 active:scale-[.97]"
          >
            Start for free
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.7}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M8 12h8m-3.5-3.5L16 12l-3.5 3.5" />
            </svg>
          </button>
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2.5 rounded-pill border border-lilac-50/[0.14] bg-lilac-50/[0.06] px-6 py-4 text-[15px] font-semibold text-lilac-50 backdrop-blur-[14px] transition hover:bg-lilac-50/[0.12] hover:text-lilac-50"
          >
            {/* #documentation-icon from public/icons.svg */}
            <svg
              className="h-[18px] w-[18px]"
              viewBox="0 0 21 20"
              fill="none"
              stroke="#C9A9FF"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.35}
            >
              <path d="m15.5 13.333 1.533 1.322c.645.555.967.833.967 1.178s-.322.623-.967 1.179L15.5 18.333m-3.333-5-1.534 1.322c-.644.555-.966.833-.966 1.178s.322.623.966 1.179l1.534 1.321" />
              <path d="M17.167 10.836v-4.32c0-1.41 0-2.117-.224-2.68-.359-.906-1.118-1.621-2.08-1.96-.599-.21-1.349-.21-2.848-.21-2.623 0-3.935 0-4.983.369-1.684.591-3.013 1.842-3.641 3.428C3 6.449 3 7.684 3 10.154v2.122c0 2.558 0 3.838.706 4.726q.306.383.713.671c.76.536 1.79.64 3.581.66" />
              <path d="M3 10a2.78 2.78 0 0 1 2.778-2.778c.555 0 1.209.097 1.748-.047.48-.129.854-.503.982-.982.145-.54.048-1.194.048-1.749a2.78 2.78 0 0 1 2.777-2.777" />
            </svg>
            Read the docs
          </a>
        </div>

        {/* Kept in step with api/validation.ts — these are the limits enforced. */}
        <div className="animate-fade-in mt-[26px] flex w-full flex-wrap items-center justify-center gap-x-[22px] gap-y-2 text-center text-xs font-medium tracking-[.06em] uppercase text-lilac-50/34 [animation-delay:.5s]">
          <span>MP4, MOV, AVI, MKV or WEBM</span>
          <span className="opacity-50">·</span>
          <span>up to 90 seconds</span>
          <span className="opacity-50">·</span>
          <span>up to 500 MB</span>
          <span className="opacity-50">·</span>
          <span>OAuth only, no passwords</span>
        </div>

        <ProductPreview />
      </div>
    </div>
  )
}
