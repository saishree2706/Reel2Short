/**
 * UploadStatus — polls upload job progress and shows the result.
 *
 * Status flow: queued → authorizing → uploading → processing → completed/failed
 * Scheduling extra status: scheduled (uploaded, waiting for YouTube to publish)
 *
 * For scheduled uploads shows the scheduled time + reschedule/cancel actions.
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import api from '../services/api'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'

type UploadStatusType =
  | 'queued'
  | 'authorizing'
  | 'uploading'
  | 'processing'
  | 'scheduled'
  | 'completed'
  | 'failed'

interface UploadRecord {
  id: string
  video_asset_id: string
  title: string
  privacy: string
  status: UploadStatusType
  bytes_uploaded: number | null
  total_bytes: number | null
  youtube_video_id: string | null
  youtube_url: string | null
  error_message: string | null
  upload_confirmed: string
  upload_mode: string
  publish_at: string | null
  scheduled_timezone: string | null
  scheduled_at: string | null
  completed_at: string | null
}

const STATUS_STEPS: Exclude<UploadStatusType, 'failed' | 'scheduled'>[] = [
  'queued',
  'authorizing',
  'uploading',
  'processing',
  'completed',
]

const STATUS_LABELS: Record<UploadStatusType, string> = {
  queued: 'Queued',
  authorizing: 'Authorizing',
  uploading: 'Uploading',
  processing: 'Processing',
  scheduled: 'Scheduled',
  completed: 'Completed',
  failed: 'Failed',
}

const STATUS_DESCRIPTIONS: Record<UploadStatusType, string> = {
  queued: 'Waiting for the worker to pick up the job…',
  authorizing: 'Verifying your YouTube credentials…',
  uploading: 'Uploading to YouTube…',
  processing: 'YouTube is processing your video…',
  scheduled: 'Uploaded! YouTube will publish at the scheduled time.',
  completed: 'Upload complete!',
  failed: 'Upload failed.',
}

const POLL_INTERVAL_MS = 3000

export default function UploadStatus() {
  const { uploadId } = useParams<{ uploadId: string }>()
  const navigate = useNavigate()

  const [upload, setUpload] = useState<UploadRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Reschedule modal state
  const [rescheduling, setRescheduling] = useState(false)
  const [newDate, setNewDate] = useState('')
  const [newTime, setNewTime] = useState('')
  const [newTz, setNewTz] = useState('')
  const [rescheduleError, setRescheduleError] = useState<string | null>(null)
  const [rescheduleSubmitting, setRescheduleSubmitting] = useState(false)
  const [cancelSubmitting, setCancelSubmitting] = useState(false)

  useEffect(() => {
    if (!uploadId) return
    fetchUpload()
    startPolling()
    return () => stopPolling()
  }, [uploadId])

  async function fetchUpload() {
    try {
      const resp = await api.get(`/api/youtube/uploads/${uploadId}`)
      setUpload(resp.data)
      setLoading(false)
      // Stop polling once we reach a terminal state
      if (['completed', 'failed', 'scheduled'].includes(resp.data.status)) {
        stopPolling()
      }
      // Pre-populate reschedule form with existing timezone
      if (resp.data.scheduled_timezone && !newTz) {
        setNewTz(resp.data.scheduled_timezone)
      }
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to load upload status.')
      setLoading(false)
      stopPolling()
    }
  }

  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(fetchUpload, POLL_INTERVAL_MS)
  }

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function handleReschedule() {
    if (!newDate || !newTime) {
      setRescheduleError('Please choose a date and time.')
      return
    }
    try {
      setRescheduleSubmitting(true)
      setRescheduleError(null)
      const resp = await api.post(`/api/youtube/uploads/${uploadId}/reschedule`, {
        scheduled_at: `${newDate}T${newTime}:00`,
        scheduled_timezone: newTz,
      })
      setUpload(resp.data)
      setRescheduling(false)
    } catch (e: any) {
      setRescheduleError(e?.userMessage || 'Failed to reschedule.')
    } finally {
      setRescheduleSubmitting(false)
    }
  }

  async function handleCancelSchedule() {
    if (!window.confirm('Cancel the scheduled publish? The video will remain private on YouTube.')) return
    try {
      setCancelSubmitting(true)
      const resp = await api.post(`/api/youtube/uploads/${uploadId}/cancel-schedule`)
      setUpload(resp.data)
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to cancel schedule.')
    } finally {
      setCancelSubmitting(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Spinner /></div>
  }
  if (error && !upload) return <ErrorAlert message={error} />
  if (!upload) return null

  const status = upload.status
  const isTerminal = ['completed', 'failed', 'scheduled'].includes(status)
  const isScheduled = status === 'scheduled'

  // For step progress display — treat 'scheduled' like 'completed' in the step flow
  const displayStatus = isScheduled ? 'completed' : status
  const currentStepIndex = STATUS_STEPS.indexOf(displayStatus as any)

  const percentage =
    upload.bytes_uploaded && upload.total_bytes && upload.total_bytes > 0
      ? Math.round((upload.bytes_uploaded / upload.total_bytes) * 100)
      : null

  function formatPublishAt(publishAt: string | null, tz: string | null): string {
    if (!publishAt) return 'Unknown'
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

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Upload Status</h1>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {/* Progress steps */}
      <div className="bg-white rounded-xl shadow p-6 space-y-5">
        <div className="space-y-3">
          {STATUS_STEPS.map((step, i) => {
            const isCompleted = status === 'completed' || isScheduled
            const isDone = i < currentStepIndex || (isCompleted && i === currentStepIndex)
            const isActive = i === currentStepIndex && !isCompleted && status !== 'failed'
            const isFailed = status === 'failed' && i === currentStepIndex
            return (
              <div key={step} className="flex items-center gap-3">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                    isDone
                      ? 'bg-green-100 text-green-700'
                      : isActive
                      ? 'bg-blue-100 text-blue-700'
                      : isFailed
                      ? 'bg-red-100 text-red-700'
                      : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {isDone ? '✓' : isActive ? <Spinner /> : i + 1}
                </div>
                <div className="flex-1">
                  <p
                    className={`text-sm font-medium ${
                      isDone
                        ? 'text-green-700'
                        : isActive
                        ? 'text-blue-700'
                        : isFailed
                        ? 'text-red-700'
                        : 'text-gray-400'
                    }`}
                  >
                    {STATUS_LABELS[step]}
                  </p>
                  {isActive && (
                    <p className="text-xs text-gray-500">{STATUS_DESCRIPTIONS[step]}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Upload progress bar */}
        {status === 'uploading' && percentage !== null && (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-gray-500">
              <span>Uploading…</span>
              <span>{percentage}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${percentage}%` }}
              />
            </div>
            {upload.total_bytes && (
              <p className="text-xs text-gray-400 text-right">
                {formatBytes(upload.bytes_uploaded || 0)} / {formatBytes(upload.total_bytes)}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Failed */}
      {status === 'failed' && (
        <div className="bg-white rounded-xl shadow p-6 space-y-4">
          <ErrorAlert message={upload.error_message || 'Upload failed for an unknown reason.'} />
          <div className="flex gap-3">
            <button
              onClick={() => navigate(-1)}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium"
            >
              ← Try Again
            </button>
            <Link
              to="/videos"
              className="px-5 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50"
            >
              My Videos
            </Link>
          </div>
        </div>
      )}

      {/* Scheduled — uploaded, waiting for YouTube */}
      {isScheduled && upload.youtube_url && (
        <div className="bg-white rounded-xl shadow p-6 space-y-5">
          <div className="flex items-center gap-3 text-indigo-700">
            <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center text-xl">📅</div>
            <div>
              <p className="font-semibold text-lg">Scheduled for Publishing!</p>
              <p className="text-sm text-gray-500">Uploaded to YouTube — will go live at the scheduled time.</p>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 space-y-1.5 text-sm">
            <p><span className="font-medium">Title:</span> {upload.title}</p>
            <p>
              <span className="font-medium">Scheduled for:</span>{' '}
              <span className="text-indigo-700 font-semibold">
                {formatPublishAt(upload.publish_at, upload.scheduled_timezone)}
              </span>
            </p>
            {upload.youtube_video_id && (
              <p>
                <span className="font-medium">Video ID:</span>{' '}
                <span className="font-mono text-xs">{upload.youtube_video_id}</span>
              </p>
            )}
          </div>

          <div className="bg-blue-50 border border-blue-200 text-blue-800 text-xs rounded-lg p-2.5">
            YouTube will automatically publish this video at the scheduled time.
            Local file has been deleted after confirmed upload.
          </div>

          <div className="flex flex-col gap-2">
            <a
              href={upload.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-center transition"
            >
              ▶ View on YouTube (Private)
            </a>

            {!rescheduling ? (
              <div className="flex gap-2">
                <button
                  onClick={() => setRescheduling(true)}
                  className="flex-1 py-2 border border-indigo-400 text-indigo-700 rounded-lg text-sm font-medium hover:bg-indigo-50"
                >
                  📅 Reschedule
                </button>
                <button
                  onClick={handleCancelSchedule}
                  disabled={cancelSubmitting}
                  className="flex-1 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
                >
                  {cancelSubmitting ? 'Cancelling…' : '✕ Cancel Schedule'}
                </button>
              </div>
            ) : (
              <div className="border border-indigo-200 rounded-lg p-4 space-y-3 bg-indigo-50">
                <p className="text-sm font-semibold text-indigo-800">Reschedule</p>
                {rescheduleError && (
                  <ErrorAlert message={rescheduleError} onDismiss={() => setRescheduleError(null)} />
                )}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Date</label>
                    <input
                      type="date"
                      value={newDate}
                      onChange={e => setNewDate(e.target.value)}
                      min={new Date().toISOString().split('T')[0]}
                      className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Time</label>
                    <input
                      type="time"
                      value={newTime}
                      onChange={e => setNewTime(e.target.value)}
                      className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Timezone</label>
                  <input
                    type="text"
                    value={newTz}
                    onChange={e => setNewTz(e.target.value)}
                    placeholder="Asia/Kolkata"
                    className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleReschedule}
                    disabled={rescheduleSubmitting}
                    className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold disabled:opacity-50"
                  >
                    {rescheduleSubmitting ? 'Saving…' : 'Save New Time'}
                  </button>
                  <button
                    onClick={() => { setRescheduling(false); setRescheduleError(null) }}
                    className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <Link
              to="/youtube/history"
              className="w-full py-2.5 border border-gray-300 text-gray-700 rounded-lg text-center text-sm font-medium hover:bg-gray-50 transition"
            >
              View Upload History
            </Link>
          </div>
        </div>
      )}

      {/* Completed (upload_now) */}
      {status === 'completed' && upload.youtube_url && (
        <div className="bg-white rounded-xl shadow p-6 space-y-5">
          <div className="flex items-center gap-3 text-green-700">
            <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center text-xl">✓</div>
            <div>
              <p className="font-semibold text-lg">Upload Complete!</p>
              <p className="text-sm text-gray-500">Your video is on YouTube.</p>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 space-y-1 text-sm">
            <p><span className="font-medium">Title:</span> {upload.title}</p>
            <p>
              <span className="font-medium">Privacy:</span>{' '}
              {upload.privacy.charAt(0).toUpperCase() + upload.privacy.slice(1)}
            </p>
            {upload.youtube_video_id && (
              <p>
                <span className="font-medium">Video ID:</span>{' '}
                <span className="font-mono text-xs">{upload.youtube_video_id}</span>
              </p>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <a
              href={upload.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-center transition"
            >
              ▶ Watch on YouTube
            </a>
            <Link
              to="/videos"
              className="w-full py-3 border border-gray-300 text-gray-700 rounded-lg text-center text-sm font-medium hover:bg-gray-50 transition"
            >
              Upload Another Video
            </Link>
          </div>
        </div>
      )}

      {/* Footer info */}
      <div className="text-xs text-gray-400 text-center space-y-1">
        <p>Upload ID: <span className="font-mono">{uploadId}</span></p>
        {!isTerminal && <p>Auto-refreshing every {POLL_INTERVAL_MS / 1000}s…</p>}
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
