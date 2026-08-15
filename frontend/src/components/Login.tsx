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

export default function Login() {
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
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-ink-900 px-4 py-12 sm:px-6 lg:px-8">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
        <div
          className="animate-drift-a absolute -top-[300px] left-1/2 h-[620px] w-[880px] -translate-x-1/2 rounded-full blur-[40px]"
          style={{ background: 'radial-gradient(closest-side, rgba(134,59,255,.30), transparent)' }}
        />
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'linear-gradient(rgba(237,230,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(237,230,255,.035) 1px, transparent 1px)',
            backgroundSize: '72px 72px',
            maskImage: 'radial-gradient(120% 80% at 50% 0%, #000 25%, transparent 78%)',
            WebkitMaskImage: 'radial-gradient(120% 80% at 50% 0%, #000 25%, transparent 78%)',
          }}
        />
      </div>

      <div className="glass-overlay animate-rise relative z-10 w-full max-w-md space-y-8 rounded-[28px] p-10 text-center">
        <div>
          <div className="flex items-center justify-center gap-2.5">
            <BoltLogo width={24} height={23} />
            <span className="font-display text-[15px] font-bold tracking-[-.01em] text-lilac-50">
              Reel Automation
            </span>
          </div>
          <h2 className="mt-6 font-display text-[30px] leading-tight font-bold tracking-[-.03em] text-lilac-50">
            Sign in to Reel Automation
          </h2>
          <p className="mt-4 text-[14.5px] text-lilac-50/62">
            Welcome back. Please sign in with your LinkedIn account to access your dashboard.
          </p>
        </div>

        {msg && (
          <div
            className={`rounded-xl border p-4 text-left text-[13.5px] ${
              msg.type === 'error'
                ? 'border-status-failed/[0.26] bg-status-failed/[0.09] text-[#FDA4AF]'
                : 'border-status-queued/[0.26] bg-status-queued/[0.09] text-[#93C5FD]'
            }`}
          >
            {msg.text}
          </div>
        )}

        <div className="mt-8">
          <button
            type="button"
            onClick={() => {
              window.location.href = '/api/auth/linkedin/login'
            }}
            className="flex w-full items-center justify-center gap-3 rounded-pill bg-[#0a66c2] px-4 py-3 text-sm font-semibold text-white shadow-[0_6px_22px_rgba(10,102,194,.35)] transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0a66c2]"
          >
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            Sign in with LinkedIn
          </button>
        </div>
      </div>
    </div>
  )
}
