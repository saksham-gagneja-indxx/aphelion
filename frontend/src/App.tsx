import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { getMe, logout, onSessionChangedInAnotherTab, type User } from './api/auth'
import { getAdminStats } from './api/admin'
import { CurrentUserProvider } from './current-user'
import { UndoProvider } from './undo'
import BoltLogo from './components/BoltLogo'
import Landing from './components/Landing'
import Compose from './pages/Compose'
import Queue from './pages/Queue'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import Docs from './pages/Docs'
import Setup from './pages/Setup'
import Admin from './pages/Admin'
import { BANNER_DANGER, BTN_OUTLINE } from './ui'

/**
 * The 72px hairline grid. Static and flat — this system has no aurora, no
 * blur and no drifting gradients; depth comes from 1px rules alone.
 */
export function GridBackdrop() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0"
      style={{
        backgroundImage:
          'linear-gradient(#272727 1px, transparent 1px), linear-gradient(90deg, #272727 1px, transparent 1px)',
        backgroundSize: '72px 72px',
        maskImage: 'linear-gradient(180deg, rgba(0,0,0,.5), transparent 60%)',
        WebkitMaskImage: 'linear-gradient(180deg, rgba(0,0,0,.5), transparent 60%)',
      }}
    />
  )
}

/** Full-page shell for the pre-authentication states. */
function AuthGate({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-ink-950 px-4 py-12">
      <GridBackdrop />
      <div className="relative z-10 w-full max-w-md">{children}</div>
    </div>
  )
}

/**
 * Avatar menu holding Settings and Sign out.
 *
 * Opens on CLICK, not hover. The previous group-hover version could not be
 * opened by touch at all, which left anyone on a phone with no way to reach
 * sign-out — the menu was the only place it existed.
 */
function UserMenu({ user }: { user: User }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const location = useLocation()

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      // Invalidate 'me' to immediately trigger the login gate
      queryClient.setQueryData(['me'], null)
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })

  // Navigating away should dismiss it, or it hangs over the new page.
  useEffect(() => setOpen(false), [location.pathname])

  useEffect(() => {
    if (!open) return
    // pointerdown rather than click: fires before the button's own handler on
    // touch, so tapping the trigger again closes rather than re-opening.
    const onPointerDown = (e: PointerEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const connected = user.linkedin_connected

  /* The ring around the avatar carries connection state now — a glanceable
     dot beats a sentence, and it frees the header on narrow screens where the
     text was hidden anyway. Green and red are the two colours outside the
     violet/white/black palette: they are the one convention nobody has to be
     taught, and the meaning is spelled out in the menu below and in the
     screen-reader label, so the colour is never the only carrier. */
  const ringClass = connected ? 'ring-online' : 'ring-danger'

  return (
    <div className="flex items-center gap-4">
      <div ref={menuRef} className="relative">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label={`Account menu — LinkedIn ${connected ? 'connected' : 'not connected'}`}
          /* min-h-11: a 44px target, below which taps start missing. */
          className="flex min-h-11 items-center gap-2.5 pl-1"
        >
          <span
            title={connected ? 'LinkedIn connected' : 'LinkedIn not connected'}
            className={`inline-flex shrink-0 rounded-full ring-2 ring-offset-2 ring-offset-ink-950 ${ringClass}`}
          >
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt=""
                className="h-7 w-7 rounded-full object-cover"
              />
            ) : (
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-900 text-[13px] text-violet-200">
                {user.name.charAt(0).toUpperCase()}
              </span>
            )}
          </span>
          <span className="hidden max-w-[140px] truncate text-[15px] text-mist-200 sm:inline">
            {user.name}
          </span>
          <svg
            aria-hidden="true"
            className={`h-4 w-4 shrink-0 text-mist-500 transition ${open ? 'rotate-180' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>

        {open && (
          <div
            role="menu"
            /* Anchored left below sm: the header wraps at that width, which
               puts the avatar on the LEFT, and a right-anchored menu then
               hangs off the side of the screen. */
            className="surface-raised absolute left-0 z-30 mt-2 w-60 max-w-[calc(100vw-2rem)] origin-top-left sm:left-auto sm:right-0 sm:origin-top-right"
          >
            <div className="border-b border-line px-4 py-3">
              <p className="truncate text-[15px] text-mist-50">{user.name}</p>
              {user.email && (
                <p className="mt-0.5 truncate text-[13px] text-mist-500">{user.email}</p>
              )}
              {/* The words behind the ring. Same two colours, so the menu
                  teaches what the avatar is signalling. */}
              <span
                className={`mt-2 inline-flex items-center gap-2 text-[13px] ${
                  connected ? 'text-online' : 'text-danger-soft'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-online' : 'bg-danger'}`}
                />
                {connected ? 'LinkedIn connected' : 'LinkedIn not connected'}
              </span>
            </div>

            <NavLink
              to="/setup"
              role="menuitem"
              className="block px-4 py-3 text-[15px] text-mist-200 transition hover:bg-ink-900 hover:text-mist-50"
            >
              Setup guide
            </NavLink>
            <NavLink
              to="/settings"
              role="menuitem"
              className="block px-4 py-3 text-[15px] text-mist-200 transition hover:bg-ink-900 hover:text-mist-50"
            >
              Settings
            </NavLink>
            <NavLink
              to="/docs"
              role="menuitem"
              className="block px-4 py-3 text-[15px] text-mist-200 transition hover:bg-ink-900 hover:text-mist-50"
            >
              Docs
            </NavLink>

            <button
              type="button"
              role="menuitem"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
              className="block w-full border-t border-line px-4 py-3 text-left text-[15px] text-danger transition hover:bg-danger/10 disabled:opacity-40"
            >
              {logoutMutation.isPending ? 'Signing out…' : 'Sign out'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const queryClient = useQueryClient()
  const { data: user, isPending, isError, error } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    retry: false, // Don't retry auth checks aggressively
  })

  // Sign-in happens in a tab we open, so the token arrives in localStorage
  // rather than through anything this tab did. Without this the page would sit
  // on the landing screen until manually reloaded.
  useEffect(
    () => onSessionChangedInAnotherTab(() => {
      void queryClient.invalidateQueries({ queryKey: ['me'] })
    }),
    [queryClient],
  )

  // Global loading state while checking session
  if (isPending) {
    return (
      <AuthGate>
        <div className="text-center">
          <div className="inline-block h-7 w-7 animate-spin rounded-full border-2 border-solid border-violet-500 border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-4 text-[16px] text-mist-500">Checking authentication…</p>
        </div>
      </AuthGate>
    )
  }

  // If 401 Unauthorized, show the landing page — it is also the sign-in gate
  if (isError && error.message === 'Unauthorized') {
    return <Landing />
  }

  // If 403 Forbidden, show awaiting approval
  if (isError && error.message === 'Forbidden') {
    return (
      <AuthGate>
        <div className="surface p-10 text-center">
          <h2 className="font-display text-[32px] font-light tracking-[-.02em] text-mist-50">
            Account Pending
          </h2>
          <p className="mt-3 text-[16px] leading-[1.6] text-mist-500">
            Your account is awaiting admin approval. Please check back later.
          </p>
          <button
            type="button"
            onClick={() => {
              // Clear any stored token so they can try again with a different account if needed
              localStorage.removeItem('smm.session')
              window.location.reload()
            }}
            className={`${BTN_OUTLINE} mt-8 w-full`}
          >
            Sign in with a different account
          </button>
        </div>
      </AuthGate>
    )
  }

  // If other error, show a generic error state
  if (isError || !user) {
    return (
      <AuthGate>
        <div className={`${BANNER_DANGER} text-center`}>
          <p className="text-[16px] text-danger-soft">Authentication Service Error</p>
          <p className="mt-1 text-[15px] text-danger-soft/70">
            {error?.message || 'Failed to verify session'}
          </p>
        </div>
      </AuthGate>
    )
  }

  // Settings and Docs deliberately live in the avatar menu rather than here:
  // they are visited rarely, and the nav has to survive a 375px screen.
  const navItems: { to: string; label: string }[] = [
    { to: '/compose', label: 'New post' },
    { to: '/queue', label: 'Queue' },
    { to: '/analytics', label: 'Analytics' },
  ]

  if (user.role === 'admin') {
    navItems.push({ to: '/admin', label: 'Admin' })
  }

  return <Shell user={user} navItems={navItems} />
}

/**
 * The signed-in chrome.
 *
 * Split out of App so the pending-approval poll can be a hook without running
 * before the auth checks above have decided whether there is a user at all.
 */
function Shell({
  user,
  navItems,
}: {
  user: User
  navItems: { to: string; label: string }[]
}) {
  // New accounts land inactive and nothing else announces them, so without
  // this an admin only discovers a waiting user by opening the panel on spec.
  const location = useLocation()

  const { data: stats } = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: getAdminStats,
    enabled: user.role === 'admin',
    refetchInterval: 60_000,
    retry: false,
  })
  const pendingApprovals = stats?.users.pending_approval ?? 0

  return (
    <div className="relative min-h-full bg-ink-950">
      <GridBackdrop />

      <header className="sticky top-0 z-20 border-b border-line bg-ink-950">
        {/* Wraps below ~975px: the six nav items plus the user block do not
            fit a laptop-narrow window, and a horizontally scrolling header is
            worse than a two-row one. */}
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-y-3 px-7 py-4">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
            <div className="flex items-center gap-2.5">
              <BoltLogo className="text-violet-500" />
              <span className="font-display text-[16px] font-medium tracking-[-.01em] whitespace-nowrap text-mist-50">
                Reel Automation
              </span>
            </div>
            {/* Scrolls within its own bounds. An earlier -mx-7/px-7 edge-bleed
                made this 3px wider than the viewport, which scrolled the whole
                document sideways on a phone. */}
            <nav className="flex max-w-full items-center gap-1 overflow-x-auto">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  /* Active is a violet underline, not a filled chip — the fill
                     treatment belongs to the primary button alone. */
                  className={({ isActive }) =>
                    `flex shrink-0 items-center gap-2 border-b-2 px-3 py-1.5 text-[15px] whitespace-nowrap transition ${
                      isActive
                        ? 'border-violet-500 text-mist-50'
                        : 'border-transparent text-mist-500 hover:text-mist-50'
                    }`
                  }
                >
                  {item.label}
                  {item.to === '/admin' && pendingApprovals > 0 && (
                    <span
                      title={`${pendingApprovals} account(s) waiting for approval`}
                      className="inline-flex min-w-[18px] items-center justify-center border border-violet-500/50 bg-violet-900 px-1 text-[12px] text-violet-200"
                    >
                      {pendingApprovals}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          </div>
          <UserMenu user={user} />
        </div>
      </header>

      {/* An unconnected account can navigate anywhere, but nothing it does
          will publish, so the reason follows it around rather than being
          discoverable only from the page it happens to be on. */}
      {!user.linkedin_connected && location.pathname !== '/setup' && (
        <div className="relative z-10 border-b border-violet-500/30 bg-violet-500/[0.07]">
          <div className="mx-auto flex max-w-[1280px] flex-wrap items-center gap-x-4 gap-y-2 px-7 py-3">
            <p className="text-[15px] text-violet-200">
              LinkedIn is not connected yet — posts cannot be published.
            </p>
            <NavLink
              to="/setup"
              className="text-[15px] text-mist-50 underline underline-offset-2 hover:text-violet-200"
            >
              Finish setup
            </NavLink>
          </div>
        </div>
      )}

      <main className="relative z-10 px-7 pt-14 pb-20">
        {/* Every page below reads its user id from here rather than hardcoding
            one, so the tool acts on whoever is actually signed in. */}
        <CurrentUserProvider user={user}>
          <UndoProvider>
          <Routes>
            {/* A first-time account lands on setup rather than an upload form
                it cannot publish from. */}
            <Route
              path="/"
              element={
                <Navigate to={user.linkedin_connected ? '/compose' : '/setup'} replace />
              }
            />
            <Route path="/compose" element={<Compose />} />
            {/* Upload and Schedule are one screen now; the old paths are kept
                so existing links and bookmarks still land somewhere. */}
            <Route path="/upload" element={<Navigate to="/compose" replace />} />
            <Route path="/schedule" element={<Navigate to="/compose" replace />} />
            <Route path="/queue" element={<Queue />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/docs" element={<Docs />} />
            <Route path="/setup" element={<Setup />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
          </UndoProvider>
        </CurrentUserProvider>
      </main>
    </div>
  )
}
