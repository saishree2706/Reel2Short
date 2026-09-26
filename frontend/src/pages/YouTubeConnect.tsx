/**
 * YouTubeConnect — shows connection status and allows connecting/disconnecting
 * the YouTube account via OAuth.
 */
import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import api from '../services/api'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'

interface ConnectionStatus {
  connected: boolean
  channel_id: string | null
  channel_name: string | null
  state: string | null
}

export default function YouTubeConnect() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<ConnectionStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  useEffect(() => {
    // Handle redirect params from OAuth callback
    const connected = searchParams.get('connected')
    const oauthError = searchParams.get('error')

    if (connected === '1') {
      setSuccessMsg('YouTube account connected successfully!')
    } else if (oauthError) {
      const errMap: Record<string, string> = {
        access_denied: 'You cancelled the Google authorization.',
        state_mismatch: 'Security error: OAuth state mismatch. Please try again.',
        callback_failed: 'OAuth callback failed. Check your configuration.',
        missing_params: 'Invalid OAuth response from Google.',
      }
      setError(errMap[oauthError] || `OAuth error: ${oauthError}`)
    }

    fetchStatus()
  }, [])

  async function fetchStatus() {
    try {
      setLoading(true)
      const resp = await api.get('/api/auth/google/status')
      setStatus(resp.data)
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to load YouTube status.')
    } finally {
      setLoading(false)
    }
  }

  async function handleConnect() {
    try {
      setConnecting(true)
      setError(null)
      const resp = await api.get('/api/auth/google/connect')
      // Redirect to Google OAuth
      window.location.href = resp.data.auth_url
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to start Google authentication.')
      setConnecting(false)
    }
  }

  async function handleDisconnect() {
    if (!confirm('Disconnect your YouTube account? You will need to reconnect to upload videos.')) return
    try {
      setDisconnecting(true)
      setError(null)
      await api.post('/api/auth/google/disconnect')
      setStatus({ connected: false, channel_id: null, channel_name: null, state: null })
      setSuccessMsg('YouTube account disconnected.')
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to disconnect YouTube account.')
    } finally {
      setDisconnecting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">YouTube Connection</h1>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {successMsg && (
        <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg p-4 flex items-center gap-3">
          <span className="text-xl">✓</span>
          <span>{successMsg}</span>
        </div>
      )}

      {status?.connected ? (
        /* Connected state */
        <div className="bg-white rounded-xl shadow p-6 space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-red-600 rounded-full flex items-center justify-center text-white text-xl font-bold">
              ▶
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium">✓ YouTube Connected</p>
              <p className="text-lg font-semibold text-gray-900">{status.channel_name}</p>
              {status.channel_id && (
                <p className="text-xs text-gray-400 font-mono">{status.channel_id}</p>
              )}
            </div>
          </div>

          <div className="border-t pt-4 flex gap-3">
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="px-5 py-2 border border-red-200 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 disabled:opacity-50 transition"
            >
              {disconnecting ? 'Disconnecting…' : 'Disconnect'}
            </button>
            <Link
              to="/videos"
              className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
            >
              Upload a Video →
            </Link>
          </div>
        </div>
      ) : (
        /* Disconnected state */
        <div className="bg-white rounded-xl shadow p-6 space-y-4 text-center">
          <div className="w-16 h-16 bg-red-600 rounded-full flex items-center justify-center text-white text-3xl font-bold mx-auto">
            ▶
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Connect your YouTube channel</h2>
            <p className="text-sm text-gray-500 mt-1">
              Connect your Google account to upload converted Reels directly to YouTube.
            </p>
          </div>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition disabled:opacity-50"
          >
            {connecting ? 'Redirecting to Google…' : 'Connect YouTube'}
          </button>
          <p className="text-xs text-gray-400">
            Only requests the minimum permissions needed to upload videos.
            Your Google password is never shared with this app.
          </p>
        </div>
      )}

      {/* Google OAuth scopes info */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-600 space-y-1">
        <p className="font-medium text-gray-800">What this app requests:</p>
        <ul className="list-disc list-inside space-y-0.5">
          <li>Upload videos to your YouTube channel</li>
          <li>Read your channel name and ID</li>
        </ul>
        <p className="text-xs text-gray-400 mt-2">
          Your account credentials are stored securely on this device and never sent to third parties.
        </p>
      </div>
    </div>
  )
}

