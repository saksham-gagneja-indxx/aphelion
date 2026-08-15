import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMe, logout, type User } from './api/auth'
import Login from './components/Login'
import Upload from './pages/Upload'
import Schedule from './pages/Schedule'
import Queue from './pages/Queue'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import Admin from './pages/Admin'

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
        <span className="text-xs font-medium text-emerald-600">LinkedIn connected</span>
      ) : (
        <span className="text-xs font-medium text-amber-600">LinkedIn not connected</span>
      )}
      <div className="relative group">
        <button className="flex items-center gap-2 focus:outline-none">
          {user.avatar_url ? (
            <img src={user.avatar_url} alt={user.name} className="h-8 w-8 rounded-full object-cover bg-slate-200" />
          ) : (
            <div className="h-8 w-8 flex items-center justify-center rounded-full bg-slate-200 text-slate-600 font-semibold text-xs">
              {user.name.charAt(0).toUpperCase()}
            </div>
          )}
          <span className="text-sm font-medium text-slate-700">{user.name}</span>
        </button>
        
        {/* Dropdown menu */}
        <div className="absolute right-0 mt-2 w-48 origin-top-right rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-10">
          <button
            type="button"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            className="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
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
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-4 text-sm font-medium text-slate-600">Checking authentication…</p>
        </div>
      </div>
    )
  }

  // If 401 Unauthorized, show Login gate
  if (isError && error.message === 'Unauthorized') {
    return <Login />
  }

  // If other error, show a generic error state
  if (isError || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center max-w-sm">
          <p className="font-semibold text-red-800">Authentication Service Error</p>
          <p className="mt-2 text-sm text-red-700">{error?.message || 'Failed to verify session'}</p>
        </div>
      </div>
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
    <div className="min-h-full bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <span className="text-sm font-semibold text-slate-900">Reel Automation</span>
            <nav className="flex gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm transition ${
                      isActive
                        ? 'bg-slate-100 font-medium text-slate-900'
                        : 'text-slate-600 hover:text-slate-900'
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

      <main className="px-6 py-10">
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
