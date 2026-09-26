/** Instagram Reels browser with pagination. */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getReels, getReelStatus } from '../services/endpoints'
import type { InstagramMedia, InstagramMediaList } from '../types'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'

export function InstagramReels() {
  const [data, setData] = useState<InstagramMediaList | null>(null)
  const [cursor, setCursor] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selecting, setSelecting] = useState<string | null>(null)
  const navigate = useNavigate()

  const load = useCallback((cur?: string) => {
    setLoading(true)
    setError(null)
    getReels(cur)
      .then((d) => {
        setData((prev) =>
          cur && prev
            ? { ...d, items: [...prev.items, ...d.items] }
            : d
        )
        setCursor(d.next_cursor ?? undefined)
      })
      .catch((e) => setError(e.userMessage ?? 'Failed to load Reels'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleUseReel = async (reel: InstagramMedia) => {
    setSelecting(reel.id)
    setError(null)
    try {
      const status = await getReelStatus(reel.id)
      if (status.download_available) {
        navigate(`/reels/${reel.id}/download`, { state: { reel, status } })
      } else {
        // No media_url — go straight to manual upload with context
        navigate('/upload', { state: { reel, status } })
      }
    } catch (e: unknown) {
      const err = e as { userMessage?: string }
      setError(err.userMessage ?? 'Failed to check Reel status')
    } finally {
      setSelecting(null)
    }
  }

  return (
    <div className="p-8 max-w-5xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Instagram Reels</h2>
      <p className="text-gray-500 mb-6">Your Reels fetched from the Instagram API.</p>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {!data && loading && <Spinner />}

      {data && data.items.length === 0 && !loading && (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
          <p className="text-lg">No Reels found.</p>
          <p className="text-sm mt-1">Make sure your Instagram access token is configured and your account has Reels.</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {data?.items.map((reel) => (
          <ReelCard
            key={reel.id}
            reel={reel}
            loading={selecting === reel.id}
            onUse={() => handleUseReel(reel)}
          />
        ))}
      </div>

      {data?.has_more && (
        <div className="mt-8 flex justify-center">
          <button
            onClick={() => load(cursor)}
            disabled={loading}
            className="px-6 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Loading…' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  )
}

function ReelCard({
  reel,
  loading,
  onUse,
}: {
  reel: InstagramMedia
  loading: boolean
  onUse: () => void
}) {
  const date = reel.timestamp
    ? new Date(reel.timestamp).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden flex flex-col">
      {/* Thumbnail */}
      <div className="bg-gray-100 aspect-[9/16] relative">
        {reel.thumbnail_url ? (
          <img
            src={reel.thumbnail_url}
            alt="Reel thumbnail"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-300 text-4xl">
            🎬
          </div>
        )}
        {/* Media url indicator */}
        <span
          className={`absolute top-2 right-2 text-xs px-2 py-0.5 rounded-full font-medium ${
            reel.media_url
              ? 'bg-green-100 text-green-700'
              : 'bg-yellow-100 text-yellow-700'
          }`}
        >
          {reel.media_url ? '⬇ Downloadable' : '⚠ Manual upload'}
        </span>
      </div>

      {/* Info */}
      <div className="p-4 flex flex-col flex-1">
        {reel.caption && (
          <p className="text-sm text-gray-700 line-clamp-3 mb-2">{reel.caption}</p>
        )}
        {date && (
          <p className="text-xs text-gray-400 mb-4">{date}</p>
        )}
        <div className="mt-auto">
          <button
            onClick={onUse}
            disabled={loading}
            className="w-full py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Checking…' : 'Use This Reel'}
          </button>
        </div>
      </div>
    </div>
  )
}

