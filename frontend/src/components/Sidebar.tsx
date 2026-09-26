/** App-wide navigation sidebar. */
import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '🏠' },
  { to: '/reels', label: 'Instagram Reels', icon: '🎬' },
  { to: '/videos', label: 'My Videos', icon: '📹' },
  { to: '/upload', label: 'Manual Upload', icon: '⬆️' },
  { to: '/youtube/connect', label: 'YouTube', icon: '▶' },
  { to: '/youtube/history', label: 'Upload History', icon: '📋' },
]

export function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 text-white flex flex-col min-h-screen shrink-0">
      <div className="px-5 py-6 border-b border-gray-700">
        <h1 className="text-xl font-bold tracking-tight">Reel2Short</h1>
        <p className="text-xs text-gray-400 mt-1">Instagram → YouTube Shorts</p>
      </div>
      <nav className="flex-1 py-4">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-3 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <span>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-gray-700 text-xs text-gray-500">
        Stage 4 — AI + Scheduling
      </div>
    </aside>
  )
}
