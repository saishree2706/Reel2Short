/** Manual video upload page — used when media_url is unavailable. */
import { useState, useRef, DragEvent } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { uploadVideo } from '../services/endpoints'
import type { InstagramMedia, ReelStatusResponse } from '../types'
import { ErrorAlert } from '../components/ErrorAlert'

interface LocationState {
  reel?: InstagramMedia
  status?: ReelStatusResponse
}

const ALLOWED = ['.mp4', '.mov', 'video/mp4', 'video/quicktime']

export function ManualUpload() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as LocationState | null
  const fileRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reel = state?.reel
  const status = state?.status

  const pickFile = (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED.includes(f.type) && !['mp4', 'mov'].includes(ext ?? '')) {
      setError(`Unsupported file type. Please upload an MP4 or MOV file.`)
      return
    }
    setFile(f)
    setError(null)
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) pickFile(f)
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) pickFile(f)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const asset = await uploadVideo(file, {
        source_media_id: reel?.id,
        caption: reel?.caption ?? undefined,
        permalink: reel?.permalink ?? undefined,
        instagram_timestamp: reel?.timestamp ?? undefined,
        thumbnail_url: reel?.thumbnail_url ?? undefined,
      })
      navigate(`/videos/${asset.id}`, { replace: true })
    } catch (e: unknown) {
      const err = e as { userMessage?: string }
      setError(err.userMessage ?? 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const fmt = (bytes: number) =>
    bytes < 1024 * 1024
      ? `${(bytes / 1024).toFixed(1)} KB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`

  return (
    <div className="p-8 max-w-xl">
      {reel && (
        <Link to="/reels" className="text-sm text-indigo-600 hover:underline mb-6 inline-block">
          ← Back to Reels
        </Link>
      )}

      <h2 className="text-2xl font-bold text-gray-900 mb-2">Manual Video Upload</h2>
      <p className="text-gray-500 mb-6">
        {status && !status.download_available
          ? 'Automatic download is unavailable for this Reel. Upload the original video to continue.'
          : 'Upload an MP4 or MOV video file.'}
      </p>

      {/* Context from Instagram if we came from a reel */}
      {reel && (
        <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 mb-6">
          <p className="text-xs font-medium text-blue-700 mb-1">Selected Reel</p>
          {reel.caption && (
            <p className="text-sm text-blue-800 line-clamp-2">{reel.caption}</p>
          )}
          {reel.timestamp && (
            <p className="text-xs text-blue-500 mt-1">
              {new Date(reel.timestamp).toLocaleDateString()}
            </p>
          )}
        </div>
      )}

      {error && <div className="mb-4"><ErrorAlert message={error} onDismiss={() => setError(null)} /></div>}

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          dragOver
            ? 'border-indigo-400 bg-indigo-50'
            : 'border-gray-300 bg-gray-50 hover:border-indigo-300 hover:bg-indigo-50'
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".mp4,.mov,video/mp4,video/quicktime"
          className="hidden"
          onChange={onInputChange}
        />
        <p className="text-3xl mb-3">📁</p>
        <p className="text-sm font-medium text-gray-700">
          {file ? file.name : 'Drop video here or click to choose'}
        </p>
        <p className="text-xs text-gray-400 mt-1">Supported: MP4, MOV</p>
        {file && (
          <p className="text-xs text-gray-500 mt-2">
            {fmt(file.size)} · {file.type || 'video'}
          </p>
        )}
      </div>

      {file && (
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="mt-6 w-full py-3 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Uploading…
            </span>
          ) : (
            `⬆ Upload ${file.name}`
          )}
        </button>
      )}
    </div>
  )
}

