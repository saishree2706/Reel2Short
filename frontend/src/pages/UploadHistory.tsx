/**
 * UploadHistory — shows all YouTube upload records with status, scheduled time, and actions.
 *
 * For each upload shows:
 * - Title + status badge
 * - Scheduled for (if scheduled)
 * - YouTube URL (View / watch)
 * - For scheduled: Cancel Schedule action
 * - Upload date
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'

interface UploadRecord {
  id: string
  video_asset_id: string
  title: string
  privacy: string
  status: string
  upload_mode: string
  youtube_video_id: string | null
  youtube_url: string | null
  publish_at: string | null
  scheduled_timezone: string | null
  error_message: string | null
  upload_confirmed: string
  created_at: string
  completed_at: string | null
}

const STATUS_COLORS: Record<string, string> = {
  queued: 'bg-gray-100 text-gray-600',
  authorizing: 'bg-blue-100 text-blue-700',
  uploading: 'bg-blue-100 text-blue-700',
  processing: 'bg-yellow-100 text-yellow-700',
  scheduled: 'bg-indigo-100 text-indigo-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

const STATUS_ICONS: Record<string, string> = {
  queued: '⏳',
  authorizing: '🔑',
  uploading: '⬆️',
  processing: '⚙️',
  scheduled: '📅',
  completed: '✓',
  failed: '✗',
}

export default function UploadHistory() {
  const [uploads, setUploads] = useState<UploadRecord[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)

  useEffect(() => {
    fetchHistory()
  }, [])

  async function fetchHistory() {
    try {
      setLoading(true)
      const resp = await api.get('/api/youtube/uploads?limit=50')
      setUploads(resp.data.items || [])
      setTotal(resp.data.total || 0)
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to load upload history.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCancelSchedule(upload: UploadRecord) {
    if (!window.confirm(`Cancel scheduled publish for "${upload.title}"?\nThe video will remain private on YouTube.`)) return
    try {
      setCancellingId(upload.id)
      await api.post(`/api/youtube/uploads/${upload.id}/cancel-schedule`)
      await fetchHistory()
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to cancel schedule.')
    } finally {
      setCancellingId(null)
    }
  }

  function formatDate(iso: string): string {
    try {
      return new Date(iso).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch {
      return iso
    }
  }

  function formatPublishAt(publishAt: string | null, tz: string | null): string {
    if (!publishAt) return '—'
    try {
      const dt = new Date(publishAt)
      return dt.toLocaleString('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: tz || 'UTC',
      }) + (tz ? ` (${tz})` : ' UTC')
    } catch {
      return publishAt
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Spinner /></div>
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Upload History</h1>
          <p className="text-sm text-gray-500 mt-1">{total} upload{total !== 1 ? 's' : ''} total</p>
        </div>
        <Link
          to="/videos"
          className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50"
        >
          ← My Videos
        </Link>
      </div>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {uploads.length === 0 ? (
        <div className="bg-white rounded-xl shadow p-12 text-center space-y-3">
          <p className="text-4xl">📭</p>
          <p className="text-gray-600 font-medium">No uploads yet</p>
          <p className="text-sm text-gray-400">Upload a video to YouTube to see it here.</p>
          <Link
            to="/videos"
            className="inline-block mt-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium"
          >
            Go to My Videos
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {uploads.map(upload => (
            <div
              key={upload.id}
              className={`bg-white rounded-xl shadow-sm border-l-4 p-5 space-y-3 ${
                upload.status === 'completed'
                  ? 'border-green-400'
                  : upload.status === 'scheduled'
                  ? 'border-indigo-400'
                  : upload.status === 'failed'
                  ? 'border-red-400'
                  : 'border-gray-200'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                {/* Title + status */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold text-gray-900 truncate">{upload.title}</p>
                    <span
                      className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                        STATUS_COLORS[upload.status] || 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {STATUS_ICONS[upload.status]} {upload.status.charAt(0).toUpperCase() + upload.status.slice(1)}
                    </span>
                    {upload.upload_mode === 'scheduled' && upload.status !== 'scheduled' && (
                      <span className="text-xs text-gray-400 italic">scheduled upload</span>
                    )}
                  </div>

                  {/* Schedule time */}
                  {upload.upload_mode === 'scheduled' && upload.publish_at && (
                    <p className="text-sm text-indigo-700 mt-1">
                      📅 Scheduled for: <span className="font-medium">
                        {formatPublishAt(upload.publish_at, upload.scheduled_timezone)}
                      </span>
                    </p>
                  )}

                  {/* Error message */}
                  {upload.status === 'failed' && upload.error_message && (
                    <p className="text-sm text-red-600 mt-1 line-clamp-2">{upload.error_message}</p>
                  )}
                </div>

                {/* Upload date */}
                <div className="text-right shrink-0">
                  <p className="text-xs text-gray-400">Uploaded</p>
                  <p className="text-xs text-gray-600">{formatDate(upload.created_at)}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {upload.privacy.charAt(0).toUpperCase() + upload.privacy.slice(1)}
                  </p>
                </div>
              </div>

              {/* Actions row */}
              <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
                {/* View status / poll */}
                {!['completed', 'failed', 'scheduled'].includes(upload.status) && (
                  <Link
                    to={`/youtube/upload/${upload.id}/status`}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    View status →
                  </Link>
                )}

                {/* View on YouTube */}
                {upload.youtube_url && (
                  <a
                    href={upload.youtube_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs bg-red-50 text-red-700 hover:bg-red-100 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    ▶ View on YouTube
                  </a>
                )}

                {/* Reschedule → go to status page */}
                {upload.status === 'scheduled' && (
                  <Link
                    to={`/youtube/upload/${upload.id}/status`}
                    className="inline-flex items-center gap-1 text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    📅 Reschedule
                  </Link>
                )}

                {/* Cancel schedule */}
                {upload.status === 'scheduled' && (
                  <button
                    onClick={() => handleCancelSchedule(upload)}
                    disabled={cancellingId === upload.id}
                    className="inline-flex items-center gap-1 text-xs bg-gray-50 text-gray-600 hover:bg-gray-100 px-3 py-1.5 rounded-lg font-medium transition disabled:opacity-50"
                  >
                    {cancellingId === upload.id ? 'Cancelling…' : '✕ Cancel Schedule'}
                  </button>
                )}

                {/* Spacer / Video ID */}
                {upload.youtube_video_id && (
                  <p className="ml-auto text-xs text-gray-400 font-mono">{upload.youtube_video_id}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

