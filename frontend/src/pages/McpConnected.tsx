/**
 * Standalone landing page for the MCP self-serve link flow.
 *
 * Reached only via backend/api/auth_routes.py's linkedin_callback when the
 * LinkedIn sign-in state carries a link_github (see mcp_link_start): the
 * person got here by clicking a link inside a Claude tool response, not by
 * navigating the app, so the next thing they want is Claude, not this
 * dashboard. This page says what happened in one line and bounces them back
 * automatically - no session UI, no nav, nothing else to look at.
 *
 * Deliberately outside the authenticated app shell (see App.tsx routing it
 * before the /api/me check): a brand-new self-serve account is very often
 * still pending approval and has no working session yet, so this can't
 * assume a logged-in state the way every other page does.
 */
import { useEffect } from 'react'
import BoltLogo from '../components/BoltLogo'
import { BTN_PRIMARY } from '../ui'

const CLAUDE_URL = 'https://claude.ai/'
const REDIRECT_DELAY_MS = 2500

const COPY: Record<string, { heading: string; body: string }> = {
  connected: {
    heading: 'Connected',
    body: "Your LinkedIn account is linked. Head back to Claude and try your request again.",
  },
  pending_approval: {
    heading: 'Almost there',
    body: 'LinkedIn is connected, but your account needs the owner to approve it before Post Pilot can act on it. Head back to Claude - you can try again once approved.',
  },
  denied: {
    heading: "Didn't go through",
    body: 'LinkedIn sign-in was cancelled. Head back to Claude and try connecting again.',
  },
  not_permitted: {
    heading: "Didn't go through",
    body: "This connector isn't accepting new sign-ups right now. Head back to Claude and let the owner know.",
  },
  network_error: {
    heading: 'Something went wrong',
    body: 'LinkedIn could not be reached. Head back to Claude and try connecting again.',
  },
}

const FALLBACK = {
  heading: 'Something went wrong',
  body: 'That LinkedIn sign-in attempt failed. Head back to Claude and try connecting again.',
}

export default function McpConnected() {
  const status = new URLSearchParams(window.location.search).get('status') ?? ''
  const { heading, body } = COPY[status] ?? FALLBACK

  useEffect(() => {
    const timer = setTimeout(() => {
      window.location.href = CLAUDE_URL
    }, REDIRECT_DELAY_MS)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-ink-950 px-6 text-center">
      <BoltLogo className="mb-8 h-8 w-8 text-mist-50" />
      <h1 className="font-display text-[32px] font-light tracking-[-.02em] text-mist-50">
        {heading}
      </h1>
      <p className="mt-3 max-w-[420px] text-[15px] leading-[1.65] text-mist-500">{body}</p>
      <p className="mt-6 text-[13px] text-mist-500">Returning you to Claude…</p>
      <a href={CLAUDE_URL} className={`${BTN_PRIMARY} mt-4`}>
        Continue to Claude now
      </a>
    </div>
  )
}
