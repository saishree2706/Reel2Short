/** Dashboard — health check and quick stats. */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHealth, getVideos } from '../services/endpoints'
import type { HealthResponse, VideoAssetList } from '../types'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [videos, setVideos] = useState<VideoAssetList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getHealth(), getVideos(0, 1)])
      .then(([h, v]) => {
        setHealth(h)
        setVideos(v)
      })
      .catch((e) => setError(e.userMessage ?? 'Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  return (
    <div className="p-8 max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Dashboard</h2>
      <p className="text-gray-500 mb-8">Reel2Short — Stage 1 Local Foundation</p>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {/* Status card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <StatCard
          label="Backend"
          value={health?.status === 'ok' ? '✅ Running' : '❌ Down'}
          sub={health?.environment ?? ''}
        />
        <StatCard
          label="Instagram"
          value={health?.instagram_configured ? '✅ Configured' : '⚠️ Not configured'}
          sub="Access token in .env"
        />
        <StatCard
          label="Videos Stored"
          value={String(videos?.total ?? 0)}
          sub="downloaded + uploaded"
        />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ActionCard
          to="/reels"
          title="Browse Instagram Reels"
          description="Fetch your Reels and download or prepare them for upload."
          icon="🎬"
        />
        <ActionCard
          to="/upload"
          title="Manual Upload"
          description="Upload an MP4 or MOV file directly when automatic download is unavailable."
          icon="⬆️"
        />
        <ActionCard
          to="/videos"
          title="My Videos"
          description="View all downloaded and uploaded videos with their metadata."
          icon="📹"
        />
      </div>

      {health && (
        <details className="mt-8">
          <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
            System info
          </summary>
          <pre className="mt-2 text-xs bg-gray-100 p-3 rounded-lg overflow-auto">
            {JSON.stringify(health, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="mt-1 text-lg font-semibold text-gray-900">{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  )
}

function ActionCard({ to, title, description, icon }: { to: string; title: string; description: string; icon: string }) {
  return (
    <Link
      to={to}
      className="flex items-start gap-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all"
    >
      <span className="text-2xl">{icon}</span>
      <div>
        <p className="font-semibold text-gray-900">{title}</p>
        <p className="text-sm text-gray-500 mt-0.5">{description}</p>
      </div>
    </Link>
  )
}

