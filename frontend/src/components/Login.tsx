import { useEffect, useState } from 'react'

const MESSAGES: Record<string, { text: string; type: 'error' | 'info' }> = {
  denied: { text: 'You declined the LinkedIn authorization request. Please authorize to sign in.', type: 'error' },
  state_mismatch: { text: 'Security check failed (state mismatch). Please try signing in again.', type: 'error' },
  token_failed: { text: 'Failed to retrieve access token from LinkedIn.', type: 'error' },
  userinfo_failed: { text: 'Failed to fetch your profile from LinkedIn.', type: 'error' },
  network_error: { text: 'A network error occurred while communicating with LinkedIn.', type: 'error' },
  pending_approval: { text: 'Your account is awaiting approval.', type: 'info' },
}

const API_BASE = import.meta.env.VITE_API_URL ?? ''

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
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 rounded-xl border border-slate-200 bg-white p-10 shadow-lg text-center">
        <div>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
            Sign in to Reel Automation
          </h2>
          <p className="mt-4 text-sm text-slate-600">
            Welcome back. Please sign in with your LinkedIn account to access your dashboard.
          </p>
        </div>

        {msg && (
          <div
            className={`rounded-md p-4 text-sm text-left border ${
              msg.type === 'error'
                ? 'bg-red-50 text-red-700 border-red-200'
                : 'bg-blue-50 text-blue-700 border-blue-200'
            }`}
          >
            {msg.text}
          </div>
        )}

        <div className="mt-8">
          <button
            type="button"
            onClick={() => {
              window.location.href = `${API_BASE}/api/auth/linkedin/login`
            }}
            className="flex w-full items-center justify-center gap-3 rounded-md bg-[#0a66c2] px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[#004182] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0a66c2] transition"
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
