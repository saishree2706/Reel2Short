/** Video detail page — full metadata and in-browser playback. */
import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getVideo, deleteVideo, videoFileUrl, probeVideo } from '../services/endpoints'
import type { VideoAsset } from '../types'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { AspectRatioBadge } from '../components/AspectRatioBadge'

export function VideoDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [video, setVideo] = useState<VideoAsset | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [probing, setProbing] = useState(false)

  useEffect(() => {
    if (!id) return
    getVideo(id)
      .then(async (v) => {
        setVideo(v)
        // Auto-probe if aspect ratio or dimensions are unknown
        if (!v.width || !v.aspect_ratio || v.aspect_ratio === 'unknown') {
          try {
            setProbing(true)
            const probed = await probeVideo(id)
            setVideo((prev) => (prev ? { ...prev, ...probed, id: prev.id } : prev))
          } catch (probeErr) {
            console.warn('Auto probe failed on detail view:', probeErr)
          } finally {
            setProbing(false)
          }
        }
      })
      .catch((e) => setError(e.userMessage ?? 'Failed to load video'))
      .finally(() => setLoading(false))
  }, [id])

  const handleReprobe = async () => {
    if (!id) return
    setProbing(true)
    setError(null)
    try {
      const probed = await probeVideo(id)
      setVideo((prev) => (prev ? { ...prev, ...probed, id: prev.id } : prev))
    } catch (e: any) {
      setError(e?.userMessage ?? 'Failed to probe video with ffprobe')
    } finally {
      setProbing(false)
    }
  }

  const handleDelete = async () => {
    if (!video || !confirm('Delete this video? This cannot be undone.')) return
    setDeleting(true)
    try {
      await deleteVideo(video.id)
      navigate('/videos', { replace: true })
    } catch (e: unknown) {
      const err = e as { userMessage?: string }
      setError(err.userMessage ?? 'Delete failed')
      setDeleting(false)
    }
  }

  if (loading) return <Spinner />
  if (error) return <div className="p-8"><ErrorAlert message={error} /></div>
  if (!video) return null

  const date = new Date(video.created_at).toLocaleString('en-US', {
    dateStyle: 'medium', timeStyle: 'short',
  })

  const fmt = (bytes: number | null) =>
    bytes == null ? 'Unknown'
      : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`

  const fmtDur = (s: number | null) => {
    if (s == null) return 'Unknown'
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}m ${sec}s`
  }

  return (
    <div className="p-8 max-w-3xl">
      <Link to="/videos" className="text-sm text-indigo-600 hover:underline mb-6 inline-block">
        ← Back to Videos
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 break-all">{video.original_filename}</h2>
          <p className="text-gray-500 text-sm mt-1">Added {date}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-4">
          <Link
            to={`/videos/${video.id}/prepare`}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            Prepare for Shorts
          </Link>
          <Link
            to={`/videos/${video.id}/youtube`}
            className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
          >
            ▶ Upload to YouTube
          </Link>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="px-4 py-2 rounded-lg border border-red-200 text-red-600 text-sm font-medium hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {error && <div className="mb-4"><ErrorAlert message={error} onDismiss={() => setError(null)} /></div>}

      {/* Video player */}
      <div className="rounded-xl overflow-hidden bg-black mb-6 shadow-lg">
        <video
          src={videoFileUrl(video.id)}
          controls
          preload="metadata"
          className="w-full max-h-[500px]"
        />
      </div>

      {/* Metadata grid */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-6 mb-4">
        <h3 className="font-semibold text-gray-900 mb-4">Video Information</h3>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <MetaRow label="Source" value={
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
              video.source === 'instagram' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'
            }`}>
              {video.source === 'instagram' ? 'Instagram' : 'Manual Upload'}
            </span>
          } />
          <MetaRow label="Aspect Ratio" value={<AspectRatioBadge ratio={video.aspect_ratio} />} />
          <MetaRow label="Resolution" value={
            video.width && video.height ? `${video.width} × ${video.height}` : 'Unknown'
          } />
          <MetaRow label="Duration" value={fmtDur(video.duration_seconds)} />
          <MetaRow label="File Size" value={fmt(video.file_size)} />
          <MetaRow label="Format" value={video.mime_type ?? 'Unknown'} />
          {video.source_media_id && (
            <MetaRow label="Instagram ID" value={video.source_media_id} />
          )}
          {video.permalink && (
            <MetaRow label="Instagram Link" value={
              <a href={video.permalink} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline truncate block">
                View on Instagram ↗
              </a>
            } />
          )}
          {video.instagram_timestamp && (
            <MetaRow label="Posted" value={new Date(video.instagram_timestamp).toLocaleDateString()} />
          )}
        </dl>

        {video.caption && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Caption</p>
            <p className="text-sm text-gray-700 whitespace-pre-line">{video.caption}</p>
          </div>
        )}
      </div>

      {/* Aspect ratio guidance */}
      {video.aspect_ratio === 'unknown' && (
        <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-yellow-800">Dimensions unknown</p>
            <p className="text-xs text-yellow-600 mt-1">
              Could not detect video dimensions automatically.
            </p>
          </div>
          <button
            onClick={handleReprobe}
            disabled={probing}
            className="px-4 py-2 rounded-lg bg-yellow-600 hover:bg-yellow-700 text-white text-xs font-medium disabled:opacity-50 transition-colors"
          >
            {probing ? 'Probing…' : 'Re-probe with ffprobe'}
          </button>
        </div>
      )}
      {video.aspect_ratio === 'horizontal' && (
        <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
          <p className="text-sm font-medium text-orange-800">⚠ Horizontal video detected</p>
          <p className="text-xs text-orange-600 mt-1">
            YouTube Shorts requires 9:16 vertical format. Conversion will be available in a future stage.
          </p>
        </div>
      )}
      {video.aspect_ratio === 'vertical' && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4">
          <p className="text-sm font-medium text-green-800">✅ Vertical format — ready for YouTube Shorts</p>
          <p className="text-xs text-green-600 mt-1">
            This video is in the correct 9:16 aspect ratio for YouTube Shorts upload.
          </p>
        </div>
      )}
    </div>
  )
}

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</dt>
      <dd className="mt-1 text-gray-900">{value}</dd>
    </div>
  )
}

