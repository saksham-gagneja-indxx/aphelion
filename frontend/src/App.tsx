import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMe, logout, type User } from './api/auth'
import BoltLogo from './components/BoltLogo'
import Landing from './components/Landing'
import Upload from './pages/Upload'
import Schedule from './pages/Schedule'
import Queue from './pages/Queue'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
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

function UserMenu({ user }: { user: User }) {
  const queryClient = useQueryClient()
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      // Invalidate 'me' to immediately trigger the login gate
      queryClient.setQueryData(['me'], null)
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })

  return (
    <div className="flex items-center gap-4">
      {/* Connection state reads in violet or grey — the status palette is
          reserved for posts, and this is not one. */}
      {user.linkedin_connected ? (
        <span className="hidden items-center gap-2 text-[14px] whitespace-nowrap text-mist-200 md:inline-flex">
          <span className="h-1.5 w-1.5 rounded-full bg-violet-500" />
          LinkedIn connected
        </span>
      ) : (
        <span className="hidden items-center gap-2 text-[14px] whitespace-nowrap text-mist-500 md:inline-flex">
          <span className="h-1.5 w-1.5 rounded-full bg-mist-500" />
          LinkedIn not connected
        </span>
      )}
      <div className="group relative">
        <button className="flex items-center gap-2.5">
          {user.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.name}
              className="h-7 w-7 rounded-full object-cover"
            />
          ) : (
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-900 text-[13px] text-violet-200">
              {user.name.charAt(0).toUpperCase()}
            </div>
          )}
          <span className="hidden text-[15px] whitespace-nowrap text-mist-200 sm:inline">
            {user.name}
          </span>
        </button>

        {/* Dropdown menu */}
        <div className="surface-raised invisible absolute right-0 z-20 mt-2 w-48 origin-top-right opacity-0 transition-all duration-150 group-hover:visible group-hover:opacity-100">
          <button
            type="button"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            className="block w-full px-4 py-2.5 text-left text-[15px] text-mist-200 transition hover:bg-ink-900 hover:text-mist-50 disabled:opacity-40"
          >
            {logoutMutation.isPending ? 'Signing out...' : 'Sign out'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const { data: user, isPending, isError, error } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    retry: false, // Don't retry auth checks aggressively
  })

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

  const navItems = [
    { to: '/upload', label: 'Upload' },
    { to: '/schedule', label: 'Schedule' },
    { to: '/queue', label: 'Queue' },
    { to: '/analytics', label: 'Analytics' },
    { to: '/settings', label: 'Settings' },
  ]

  if (user.role === 'admin') {
    navItems.push({ to: '/admin', label: 'Admin' })
  }

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
            <nav className="flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  /* Active is a violet underline, not a filled chip — the fill
                     treatment belongs to the primary button alone. */
                  className={({ isActive }) =>
                    `border-b-2 px-3 py-1.5 text-[15px] whitespace-nowrap transition ${
                      isActive
                        ? 'border-violet-500 text-mist-50'
                        : 'border-transparent text-mist-500 hover:text-mist-50'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <UserMenu user={user} />
        </div>
      </header>

      <main className="relative z-10 px-7 pt-14 pb-20">
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </main>
    </div>
  )
}
