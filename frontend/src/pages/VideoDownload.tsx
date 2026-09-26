/** Video download page — triggered from a Reel with media_url. */
import { useState } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { downloadReel } from '../services/endpoints'
import type { InstagramMedia, ReelStatusResponse } from '../types'
import { ErrorAlert } from '../components/ErrorAlert'
import { Spinner } from '../components/Spinner'

interface LocationState {
  reel: InstagramMedia
  status: ReelStatusResponse
}

export function VideoDownload() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as LocationState | null

  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!state?.reel || !state?.status) {
    return (
      <div className="p-8">
        <ErrorAlert message="No Reel selected. Please go back to Instagram Reels." />
        <Link to="/reels" className="mt-4 inline-block text-indigo-600 hover:underline text-sm">
          ← Back to Reels
        </Link>
      </div>
    )
  }

  const { reel, status } = state

  // Redirect to manual upload if no media_url
  if (!status.download_available || !status.media_url) {
    return (
      <div className="p-8 max-w-lg">
        <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-6">
          <h3 className="font-semibold text-yellow-800 text-lg mb-2">Automatic download unavailable</h3>
          <p className="text-yellow-700 text-sm mb-4">
            Automatic download is unavailable for this Reel. Please upload the original video to continue.
          </p>
          <Link
            to="/upload"
            state={{ reel, status }}
            className="inline-block px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            Upload Original Video →
          </Link>
        </div>
      </div>
    )
  }

  const handleDownload = async () => {
    setDownloading(true)
    setError(null)
    try {
      const asset = await downloadReel({
        media_id: reel.id,
        media_url: status.media_url!,
        caption: reel.caption,
        permalink: reel.permalink,
        instagram_timestamp: reel.timestamp,
        thumbnail_url: reel.thumbnail_url,
      })
      navigate(`/videos/${asset.id}`, { replace: true })
    } catch (e: unknown) {
      const err = e as { userMessage?: string }
      setError(err.userMessage ?? 'Download failed')
    } finally {
      setDownloading(false)
    }
  }

  const date = reel.timestamp
    ? new Date(reel.timestamp).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : null

  return (
    <div className="p-8 max-w-xl">
      <Link to="/reels" className="text-sm text-indigo-600 hover:underline mb-6 inline-block">
        ← Back to Reels
      </Link>

      <h2 className="text-2xl font-bold text-gray-900 mb-6">Download Reel</h2>

      {error && <div className="mb-4"><ErrorAlert message={error} onDismiss={() => setError(null)} /></div>}

      {/* Reel preview card */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden mb-6">
        {reel.thumbnail_url && (
          <img src={reel.thumbnail_url} alt="Thumbnail" className="w-full h-48 object-cover" />
        )}
        <div className="p-5">
          {reel.caption && (
            <p className="text-sm text-gray-700 mb-2 line-clamp-3">{reel.caption}</p>
          )}
          {date && <p className="text-xs text-gray-400 mb-3">{date}</p>}
          {reel.permalink && (
            <a
              href={reel.permalink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-indigo-500 hover:underline"
            >
              View on Instagram ↗
            </a>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-green-200 bg-green-50 p-4 mb-6">
        <p className="text-sm text-green-700 font-medium">✅ Download available</p>
        <p className="text-xs text-green-600 mt-0.5">
          This Reel can be downloaded automatically via the Instagram API.
        </p>
      </div>

      <button
        onClick={handleDownload}
        disabled={downloading}
        className="w-full py-3 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
      >
        {downloading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Downloading… (streaming)
          </span>
        ) : (
          '⬇ Download Video'
        )}
      </button>
    </div>
  )
}

