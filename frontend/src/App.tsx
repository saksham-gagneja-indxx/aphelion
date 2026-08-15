import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMe, logout, type User } from './api/auth'
import BoltLogo from './components/BoltLogo'
import Login from './components/Login'
import Upload from './pages/Upload'
import Schedule from './pages/Schedule'
import Queue from './pages/Queue'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import Admin from './pages/Admin'

/**
 * Aurora + grid backdrop from the dark-glass handoff.
 *
 * Fixed rather than absolute so the blobs stay put while the page scrolls —
 * a 1440px design frame has no scroll, a real page does. The layered
 * gradients live in `style` because Tailwind arbitrary values get unreadable
 * once a background stacks three images with their own colour stops.
 */
function AuroraBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
      <div
        className="animate-drift-a absolute -top-[340px] left-[32%] h-[640px] w-[900px] rounded-full blur-[40px]"
        style={{ background: 'radial-gradient(closest-side, rgba(134,59,255,.30), transparent)' }}
      />
      <div
        className="animate-drift-b absolute -top-[200px] -left-[160px] h-[560px] w-[620px] rounded-full blur-[40px]"
        style={{ background: 'radial-gradient(closest-side, rgba(170,59,255,.18), transparent)' }}
      />
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(237,230,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(237,230,255,.035) 1px, transparent 1px)',
          backgroundSize: '72px 72px',
          maskImage: 'linear-gradient(180deg, #000, transparent 55%)',
          WebkitMaskImage: 'linear-gradient(180deg, #000, transparent 55%)',
        }}
      />
    </div>
  )
}

/** Full-page shell for the pre-authentication states. */
function AuthGate({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-ink-900 px-4 py-12">
      <AuroraBackdrop />
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
      {user.linkedin_connected ? (
        <span className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold whitespace-nowrap text-[#6EE7B7]">
          <span className="h-[5px] w-[5px] rounded-full bg-status-posted" />
          LinkedIn connected
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold whitespace-nowrap text-[#FCD34D]">
          <span className="h-[5px] w-[5px] rounded-full bg-status-cancelled" />
          LinkedIn not connected
        </span>
      )}
      <div className="group relative">
        <button className="flex items-center gap-[9px] focus:outline-none">
          {user.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.name}
              className="h-[30px] w-[30px] rounded-full object-cover ring-1 ring-lilac-50/[0.12]"
            />
          ) : (
            <div className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-[linear-gradient(150deg,#AA3BFF,#531ABE)] text-xs font-bold text-white ring-1 ring-lilac-50/[0.12]">
              {user.name.charAt(0).toUpperCase()}
            </div>
          )}
          <span className="text-[13.5px] font-medium whitespace-nowrap text-lilac-50/[0.82]">
            {user.name}
          </span>
        </button>

        {/* Dropdown menu */}
        <div className="glass-overlay invisible absolute right-0 z-20 mt-2 w-48 origin-top-right rounded-xl py-1 opacity-0 transition-all duration-150 group-hover:visible group-hover:opacity-100">
          <button
            type="button"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            className="block w-full px-4 py-2 text-left text-[13.5px] text-lilac-50/80 transition hover:bg-lilac-50/[0.06] hover:text-lilac-50 disabled:opacity-50"
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
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-violet-400 border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-4 text-sm font-medium text-lilac-50/62">Checking authentication…</p>
        </div>
      </AuthGate>
    )
  }

  // If 401 Unauthorized, show Login gate
  if (isError && error.message === 'Unauthorized') {
    return <Login />
  }

  // If 403 Forbidden, show awaiting approval
  if (isError && error.message === 'Forbidden') {
    return (
      <AuthGate>
        <div className="glass-overlay rounded-[28px] p-10 text-center">
          <h2 className="font-display text-[30px] font-bold tracking-[-.03em] text-lilac-50">
            Account Pending
          </h2>
          <p className="mt-4 text-[14.5px] text-lilac-50/62">
            Your account is awaiting admin approval. Please check back later.
          </p>
          <button
            type="button"
            onClick={() => {
              // Clear any stored token so they can try again with a different account if needed
              localStorage.removeItem('smm.session')
              window.location.reload()
            }}
            className="mt-8 flex w-full items-center justify-center gap-3 rounded-pill border border-lilac-50/[0.14] bg-lilac-50/[0.07] px-4 py-3 text-sm font-semibold text-lilac-50 transition hover:bg-lilac-50/[0.13]"
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
        <div className="rounded-2xl border border-status-failed/[0.28] bg-status-failed/[0.07] p-6 text-center">
          <p className="text-sm font-semibold text-[#FDA4AF]">Authentication Service Error</p>
          <p className="mt-2 text-sm text-[#FDA4AF]/85">
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
    <div className="relative min-h-full bg-ink-900">
      <AuroraBackdrop />

      <header className="sticky top-0 z-20 border-b border-lilac-50/[0.08] bg-ink-900/72 backdrop-blur-[18px]">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between px-7 py-3.5">
          <div className="flex items-center gap-7">
            <div className="flex items-center gap-[9px]">
              <BoltLogo />
              <span className="font-display text-[14.5px] font-bold tracking-[-.01em] whitespace-nowrap text-lilac-50">
                Reel Automation
              </span>
            </div>
            <nav className="flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `rounded-[9px] border px-[13px] py-[7px] text-[13.5px] whitespace-nowrap transition ${
                      isActive
                        ? 'border-lilac-50/[0.12] bg-lilac-50/[0.08] font-semibold text-lilac-50'
                        : 'border-transparent text-lilac-50/58 hover:text-lilac-50'
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

      <main className="relative z-10 px-7 pt-11 pb-16">
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
