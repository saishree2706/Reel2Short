/** Video library — list of all stored VideoAssets. */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getVideos, deleteVideo } from '../services/endpoints'
import type { VideoAsset } from '../types'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { AspectRatioBadge } from '../components/AspectRatioBadge'

export function VideoList() {
  const [videos, setVideos] = useState<VideoAsset[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    getVideos()
      .then((d) => {
        setVideos(d.items)
        setTotal(d.total)
      })
      .catch((e) => setError(e.userMessage ?? 'Failed to load videos'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this video?')) return
    setDeleting(id)
    try {
      await deleteVideo(id)
      setVideos((prev) => prev.filter((v) => v.id !== id))
      setTotal((t) => t - 1)
    } catch (e: unknown) {
      const err = e as { userMessage?: string }
      setError(err.userMessage ?? 'Delete failed')
    } finally {
      setDeleting(null)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">My Videos</h2>
          <p className="text-gray-500 text-sm mt-1">{total} video{total !== 1 ? 's' : ''} stored locally</p>
        </div>
        <div className="flex gap-3">
          <Link to="/reels" className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
            Browse Reels
          </Link>
          <Link to="/upload" className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors">
            Manual Upload
          </Link>
        </div>
      </div>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {videos.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
          <p className="text-lg mb-2">No videos yet</p>
          <p className="text-sm">Download a Reel or upload a video to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {videos.map((v) => (
            <VideoRow
              key={v.id}
              video={v}
              deleting={deleting === v.id}
              onDelete={() => handleDelete(v.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function VideoRow({ video, deleting, onDelete }: { video: VideoAsset; deleting: boolean; onDelete: () => void }) {
  const date = new Date(video.created_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })

  const fmt = (bytes: number | null) =>
    bytes == null ? '—'
      : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`

  const fmtDur = (s: number | null) =>
    s == null ? '—' : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

  return (
    <div className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      {/* Source badge */}
      <span className={`w-24 text-center shrink-0 text-xs px-2 py-1 rounded-full font-medium ${
        video.source === 'instagram' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'
      }`}>
        {video.source === 'instagram' ? 'Instagram' : 'Manual'}
      </span>

      {/* Filename + meta */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{video.original_filename}</p>
        <p className="text-xs text-gray-400 mt-0.5">
          {video.width && video.height ? `${video.width}×${video.height}` : '—'} · {fmtDur(video.duration_seconds)} · {fmt(video.file_size)} · Added {date}
        </p>
        {video.caption && (
          <p className="text-xs text-gray-500 truncate mt-0.5">{video.caption}</p>
        )}
      </div>

      {/* Aspect ratio */}
      <AspectRatioBadge ratio={video.aspect_ratio} />

      {/* Actions */}
      <div className="flex items-center gap-2 shrink-0">
        <Link
          to={`/videos/${video.id}`}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
        >
          View
        </Link>
        <button
          onClick={onDelete}
          disabled={deleting}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
        >
          {deleting ? '…' : 'Delete'}
        </button>
      </div>
    </div>
  )
}

