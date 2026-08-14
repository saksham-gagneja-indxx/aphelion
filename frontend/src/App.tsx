import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getStatus } from './api/client'
import Upload from './pages/Upload'
import Schedule from './pages/Schedule'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'

const NAV = [
  { to: '/upload', label: 'Upload' },
  { to: '/schedule', label: 'Schedule' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/settings', label: 'Settings' },
]

function ConnectionBadge() {
  const { data, isError } = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
    refetchInterval: 30_000,
  })

  if (isError) {
    return <span className="text-xs font-medium text-red-600">backend unreachable</span>
  }
  if (!data) {
    return <span className="text-xs text-slate-400">checking&hellip;</span>
  }
  return (
    <span
      className={`text-xs font-medium ${
        data.instagram_configured ? 'text-emerald-600' : 'text-amber-600'
      }`}
    >
      {data.instagram_configured ? 'Instagram connected' : 'Instagram not configured'}
    </span>
  )
}

export default function App() {
  return (
    <div className="min-h-full bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <span className="text-sm font-semibold text-slate-900">Reel Automation</span>
            <nav className="flex gap-1">
              {NAV.map((item) => (
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
          <ConnectionBadge />
        </div>
      </header>

      <main className="px-6 py-10">
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
