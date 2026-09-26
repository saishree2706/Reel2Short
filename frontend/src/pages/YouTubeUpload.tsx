/**
 * YouTubeUpload — metadata form with AI generation + upload/schedule.
 *
 * Flow:
 *  1. Loads video, YouTube status, categories, default timezone
 *  2. Shows optional AI generation panel
 *  3. User reviews/edits title/description/tags/privacy/category
 *  4. Two actions: "Upload Now" or "Schedule Short"
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import api from '../services/api'
import { Spinner } from '../components/Spinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { AspectRatioBadge } from '../components/AspectRatioBadge'

// ─── Types ───────────────────────────────────────────────────────────────────

interface VideoAsset {
  id: string
  original_filename: string
  width: number | null
  height: number | null
  duration_seconds: number | null
  aspect_ratio: string | null
  file_size: number | null
  caption: string | null
  source: string
}

interface ConnectionStatus {
  connected: boolean
  channel_name: string | null
}

interface Category {
  id: string
  name: string
}

interface ThumbnailConcept {
  concept: string
  text: string
  visual_moment: string
}

interface AIResult {
  titles: string[]
  description: string
  hashtags: string[]
  tags: string[]
  category: string
  hook: string
  thumbnail: ThumbnailConcept
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PRIVACY_OPTIONS = [
  { value: 'private', label: 'Private', desc: 'Only you can see this video' },
  { value: 'unlisted', label: 'Unlisted', desc: 'Anyone with the link can see it' },
  { value: 'public', label: 'Public', desc: 'Visible to everyone on YouTube' },
]

const CONTENT_TYPES = ['Tutorial', 'Vlog', 'Review', 'Entertainment', 'Education', 'Travel', 'Food', 'Fitness', 'Comedy', 'Other']
const TONES = ['Casual', 'Professional', 'Humorous', 'Inspirational', 'Educational', 'Energetic']

// ─── Component ───────────────────────────────────────────────────────────────

export default function YouTubeUpload() {
  const { assetId } = useParams<{ assetId: string }>()
  const navigate = useNavigate()

  // Load state
  const [asset, setAsset] = useState<VideoAsset | null>(null)
  const [ytStatus, setYtStatus] = useState<ConnectionStatus | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [defaultTimezone, setDefaultTimezone] = useState('UTC')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Metadata form
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [tagInput, setTagInput] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [privacy, setPrivacy] = useState<'private' | 'unlisted' | 'public'>('private')
  const [categoryId, setCategoryId] = useState('22')

  // Scheduling
  const [uploadMode, setUploadMode] = useState<'upload_now' | 'scheduled'>('upload_now')
  const [scheduledDate, setScheduledDate] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')
  const [scheduledTimezone, setScheduledTimezone] = useState('UTC')

  // AI panel
  const [aiOpen, setAiOpen] = useState(false)
  const [aiDescription, setAiDescription] = useState('')
  const [aiKeywords, setAiKeywords] = useState('')
  const [aiContentType, setAiContentType] = useState('')
  const [aiAudience, setAiAudience] = useState('')
  const [aiTone, setAiTone] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)
  const [aiResult, setAiResult] = useState<AIResult | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [selectedTitleIdx, setSelectedTitleIdx] = useState(0)
  const [hookExpanded, setHookExpanded] = useState(false)
  const [thumbExpanded, setThumbExpanded] = useState(false)

  // Submit
  const [submitting, setSubmitting] = useState(false)

  // ─── Load ─────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!assetId) return
    Promise.all([
      api.get(`/api/videos/${assetId}`),
      api.get('/api/auth/google/status'),
      api.get('/api/youtube/categories'),
      api.get('/api/youtube/timezone-config'),
    ])
      .then(([videoResp, ytResp, catResp, tzResp]) => {
        setAsset(videoResp.data)
        setYtStatus(ytResp.data)
        setCategories(catResp.data.categories || [])
        const tz = tzResp.data.default_timezone || 'UTC'
        setDefaultTimezone(tz)
        setScheduledTimezone(tz)

        const filename = videoResp.data.original_filename || ''
        setTitle(filename.replace(/\.[^.]+$/, '').replace(/_/g, ' '))

        // Pre-fill AI description from caption if available
        if (videoResp.data.caption) {
          setAiDescription(videoResp.data.caption.slice(0, 300))
        }
      })
      .catch((e: any) => setError(e?.userMessage || 'Failed to load video details.'))
      .finally(() => setLoading(false))
  }, [assetId])

  // ─── Tags ─────────────────────────────────────────────────────────────────

  function addTag(raw?: string) {
    const t = (raw ?? tagInput).trim().replace(/^#/, '')
    if (t && !tags.includes(t) && tags.length < 15) setTags(prev => [...prev, t])
    if (!raw) setTagInput('')
  }

  function removeTag(tag: string) {
    setTags(prev => prev.filter(t => t !== tag))
  }

  function handleTagKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag() }
  }

  // ─── AI ───────────────────────────────────────────────────────────────────

  async function handleGenerate() {
    if (!aiDescription.trim()) {
      setAiError('Please describe your Reel before generating.')
      return
    }
    try {
      setAiGenerating(true)
      setAiError(null)
      const resp = await api.post(`/api/videos/${assetId}/generate-metadata`, {
        description: aiDescription.trim(),
        keywords: aiKeywords.split(',').map(k => k.trim()).filter(Boolean),
        content_type: aiContentType || null,
        target_audience: aiAudience.trim() || null,
        tone: aiTone || null,
      })
      setAiResult(resp.data)
      setSelectedTitleIdx(0)
    } catch (e: any) {
      setAiError(e?.userMessage || 'AI generation failed. Please try again.')
    } finally {
      setAiGenerating(false)
    }
  }

  function handleAcceptAI() {
    if (!aiResult) return
    setTitle(aiResult.titles[selectedTitleIdx] || title)
    setDescription(aiResult.description)
    // Merge AI tags + hashtags (strip # from hashtags)
    const newTags = [
      ...aiResult.tags,
      ...aiResult.hashtags.map(h => h.replace(/^#/, '')),
    ]
    const combined = [...new Set([...tags, ...newTags])].slice(0, 15)
    setTags(combined)
    // Set category if we can match it
    const matchedCat = categories.find(c =>
      c.name.toLowerCase() === aiResult.category.toLowerCase()
    )
    if (matchedCat) setCategoryId(matchedCat.id)
    setAiOpen(false)
  }

  // ─── Submit ───────────────────────────────────────────────────────────────

  function buildScheduledAt(): string | null {
    if (uploadMode !== 'scheduled') return null
    if (!scheduledDate || !scheduledTime) return null
    return `${scheduledDate}T${scheduledTime}:00`
  }

  async function handleAction(mode: 'upload_now' | 'scheduled') {
    if (!title.trim()) { setError('Title is required.'); return }
    if (!ytStatus?.connected) { setError('Please connect your YouTube account first.'); return }

    if (mode === 'scheduled') {
      if (!scheduledDate || !scheduledTime) {
        setError('Please select a publish date and time for scheduling.')
        return
      }
    }

    const scheduled_at = buildScheduledAt()

    try {
      setSubmitting(true)
      setError(null)
      const resp = await api.post('/api/youtube/upload', {
        video_asset_id: assetId,
        title: title.trim(),
        description: description.trim() || null,
        tags,
        privacy,
        category_id: categoryId || null,
        upload_mode: mode,
        scheduled_at,
        scheduled_timezone: mode === 'scheduled' ? scheduledTimezone : null,
      })
      navigate(`/youtube/upload/${resp.data.id}/status`)
    } catch (e: any) {
      setError(e?.userMessage || 'Failed to start upload.')
    } finally {
      setSubmitting(false)
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Spinner /></div>
  }
  if (!asset) return <ErrorAlert message={error || 'Video not found.'} />

  const isConnected = !!ytStatus?.connected

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold text-gray-900">Upload to YouTube</h1>
        <AspectRatioBadge ratio={asset.aspect_ratio || 'unknown'} />
      </div>

      {/* YouTube connection status */}
      {isConnected ? (
        <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-4 py-2 text-sm">
          <span className="text-green-700 font-medium">✓ Connected:</span>
          <span className="text-green-800">{ytStatus.channel_name}</span>
        </div>
      ) : (
        <div className="flex items-center gap-3 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm">
          <span className="text-yellow-800">⚠ No YouTube account connected.</span>
          <Link to="/youtube/connect" className="text-indigo-600 underline font-medium">Connect now →</Link>
        </div>
      )}

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {/* Video preview */}
      <div className="bg-black rounded-lg overflow-hidden">
        <video controls className="w-full max-h-72 object-contain" preload="metadata">
          <source src={`/api/videos/${asset.id}/preview`} type="video/mp4" />
        </video>
      </div>

      {/* Instagram caption */}
      {asset.caption && (
        <div className="bg-pink-50 border border-pink-200 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-pink-800">📸 Instagram Caption</p>
            <button
              type="button"
              onClick={() => setDescription(asset.caption!)}
              className="text-xs text-pink-700 underline hover:text-pink-900"
            >
              Use as description
            </button>
          </div>
          <p className="text-sm text-pink-700 whitespace-pre-wrap line-clamp-4">{asset.caption}</p>
        </div>
      )}

      {/* ✨ AI Panel */}
      <div className="bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-200 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setAiOpen(v => !v)}
          className="w-full flex items-center justify-between px-5 py-3.5 text-left"
        >
          <span className="font-semibold text-purple-900 flex items-center gap-2">
            ✨ Generate with AI
            <span className="text-xs text-purple-500 font-normal">(optional)</span>
          </span>
          <span className="text-purple-500 text-sm">{aiOpen ? '▲ Close' : '▼ Open'}</span>
        </button>

        {aiOpen && (
          <div className="px-5 pb-5 space-y-4 border-t border-purple-200">
            {aiError && <ErrorAlert message={aiError} onDismiss={() => setAiError(null)} />}

            {/* AI inputs */}
            <div className="mt-4 space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-800 mb-1">
                  Describe your Reel <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={aiDescription}
                  onChange={e => setAiDescription(e.target.value)}
                  maxLength={2000}
                  rows={3}
                  placeholder="What happens in this video? E.g. 'Quick 30-second morning coffee routine with a French press at home'"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-purple-400"
                />
                <p className="text-xs text-gray-400 mt-0.5">{aiDescription.length}/2000 characters</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Content Type</label>
                  <select
                    value={aiContentType}
                    onChange={e => setAiContentType(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                  >
                    <option value="">Select…</option>
                    {CONTENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Tone</label>
                  <select
                    value={aiTone}
                    onChange={e => setAiTone(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                  >
                    <option value="">Select…</option>
                    {TONES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Keywords <span className="text-gray-400">(comma-separated)</span>
                </label>
                <input
                  type="text"
                  value={aiKeywords}
                  onChange={e => setAiKeywords(e.target.value)}
                  placeholder="coffee, morning, routine"
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Target Audience</label>
                <input
                  type="text"
                  value={aiAudience}
                  onChange={e => setAiAudience(e.target.value)}
                  placeholder="Coffee enthusiasts, home baristas"
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={aiGenerating || !aiDescription.trim()}
                  className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white rounded-lg text-sm font-semibold transition"
                >
                  {aiGenerating ? 'Generating…' : aiResult ? '↺ Regenerate' : '✨ Generate'}
                </button>
                {aiResult && (
                  <button
                    type="button"
                    onClick={() => setAiResult(null)}
                    className="px-3 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50"
                  >
                    Ignore
                  </button>
                )}
              </div>
            </div>

            {/* AI Results */}
            {aiResult && (
              <div className="space-y-4 border-t border-purple-100 pt-4">
                {/* Titles */}
                <div>
                  <p className="text-sm font-semibold text-gray-800 mb-2">Suggested Titles</p>
                  <div className="space-y-1.5">
                    {aiResult.titles.map((t, i) => (
                      <label
                        key={i}
                        className={`flex items-start gap-2 p-2.5 rounded-lg border cursor-pointer transition text-sm ${
                          selectedTitleIdx === i
                            ? 'border-purple-500 bg-purple-50'
                            : 'border-gray-200 hover:border-gray-400'
                        }`}
                      >
                        <input
                          type="radio"
                          name="ai-title"
                          checked={selectedTitleIdx === i}
                          onChange={() => setSelectedTitleIdx(i)}
                          className="mt-0.5 shrink-0"
                        />
                        <span>{t}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Description preview */}
                <div>
                  <p className="text-sm font-semibold text-gray-800 mb-1">Suggested Description</p>
                  <p className="text-xs text-gray-600 bg-white border rounded-lg p-2.5 line-clamp-4">
                    {aiResult.description}
                  </p>
                </div>

                {/* Tags + Hashtags */}
                <div>
                  <p className="text-sm font-semibold text-gray-800 mb-1">Suggested Tags & Hashtags</p>
                  <div className="flex flex-wrap gap-1.5">
                    {aiResult.hashtags.map(h => (
                      <span key={h} className="text-xs bg-pink-100 text-pink-700 px-2 py-0.5 rounded-full">{h}</span>
                    ))}
                    {aiResult.tags.map(t => (
                      <span key={t} className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">#{t}</span>
                    ))}
                  </div>
                </div>

                {/* Hook */}
                <div>
                  <button
                    type="button"
                    onClick={() => setHookExpanded(v => !v)}
                    className="text-sm font-semibold text-gray-800 flex items-center gap-1"
                  >
                    {hookExpanded ? '▼' : '▶'} Suggested Hook
                  </button>
                  {hookExpanded && (
                    <p className="text-sm text-gray-700 mt-1 p-2.5 bg-white border rounded-lg italic">
                      "{aiResult.hook}"
                    </p>
                  )}
                </div>

                {/* Thumbnail concept */}
                <div>
                  <button
                    type="button"
                    onClick={() => setThumbExpanded(v => !v)}
                    className="text-sm font-semibold text-gray-800 flex items-center gap-1"
                  >
                    {thumbExpanded ? '▼' : '▶'} Thumbnail Concept
                  </button>
                  {thumbExpanded && (
                    <div className="mt-1 p-3 bg-white border rounded-lg text-sm space-y-1">
                      <p><span className="font-medium">Concept:</span> {aiResult.thumbnail.concept}</p>
                      <p><span className="font-medium">Overlay text:</span> "{aiResult.thumbnail.text}"</p>
                      <p><span className="font-medium">Visual moment:</span> {aiResult.thumbnail.visual_moment}</p>
                      <p className="text-xs text-gray-400 mt-1">Note: AI suggests the concept — no image is generated.</p>
                    </div>
                  )}
                </div>

                {/* Accept button */}
                <button
                  type="button"
                  onClick={handleAcceptAI}
                  className="w-full py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-semibold"
                >
                  ✓ Accept Suggestions
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Metadata form */}
      <div className="bg-white rounded-xl shadow p-6 space-y-5">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-gray-900 mb-1">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={e => setTitle(e.target.value)}
            maxLength={100}
            required
            placeholder="Enter a title for your YouTube Short"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
          />
          <p className="text-xs text-gray-400 mt-1">{title.length}/100</p>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-900 mb-1">
            Description <span className="text-gray-400">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            maxLength={5000}
            rows={4}
            placeholder="Add a description…"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 resize-y"
          />
          <p className="text-xs text-gray-400 mt-1">{description.length}/5000</p>
        </div>

        {/* Tags */}
        <div>
          <label className="block text-sm font-medium text-gray-900 mb-1">
            Tags <span className="text-gray-400">(optional, max 15)</span>
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={tagInput}
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={handleTagKeyDown}
              placeholder="Add a tag, then press Enter"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
            />
            <button
              type="button"
              onClick={() => addTag()}
              disabled={tags.length >= 15}
              className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              Add
            </button>
          </div>
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {tags.map(tag => (
                <span
                  key={tag}
                  className="flex items-center gap-1 bg-indigo-100 text-indigo-800 text-xs font-medium px-2 py-1 rounded-full"
                >
                  #{tag}
                  <button type="button" onClick={() => removeTag(tag)} className="text-indigo-600">×</button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Privacy */}
        <div>
          <label className="block text-sm font-medium text-gray-900 mb-2">Privacy</label>
          <div className="space-y-2">
            {PRIVACY_OPTIONS.map(opt => (
              <label
                key={opt.value}
                className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition ${
                  privacy === opt.value ? 'border-indigo-600 bg-indigo-50' : 'border-gray-200 hover:border-gray-400'
                }`}
              >
                <input
                  type="radio"
                  name="privacy"
                  value={opt.value}
                  checked={privacy === opt.value}
                  onChange={() => setPrivacy(opt.value as any)}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm font-medium text-gray-900">{opt.label}</p>
                  <p className="text-xs text-gray-500">{opt.desc}</p>
                </div>
              </label>
            ))}
          </div>
          {privacy === 'public' && (
            <div className="mt-2 bg-yellow-50 border border-yellow-200 text-yellow-800 text-xs rounded-lg p-2">
              ⚠ Public videos are immediately visible to everyone on YouTube.
            </div>
          )}
        </div>

        {/* Category */}
        <div>
          <label className="block text-sm font-medium text-gray-900 mb-1">
            Category <span className="text-gray-400">(optional)</span>
          </label>
          <select
            value={categoryId}
            onChange={e => setCategoryId(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
          >
            {categories.map(cat => (
              <option key={cat.id} value={cat.id}>{cat.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Schedule Short panel */}
      <div className="bg-white rounded-xl shadow p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Schedule</h2>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => setUploadMode('upload_now')}
            className={`flex-1 py-3 rounded-lg font-semibold text-sm border-2 transition ${
              uploadMode === 'upload_now'
                ? 'border-red-500 bg-red-50 text-red-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-400'
            }`}
          >
            ▶ Upload Now
          </button>
          <button
            type="button"
            onClick={() => setUploadMode('scheduled')}
            className={`flex-1 py-3 rounded-lg font-semibold text-sm border-2 transition ${
              uploadMode === 'scheduled'
                ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-400'
            }`}
          >
            📅 Schedule Short
          </button>
        </div>

        {uploadMode === 'upload_now' && (
          <p className="text-xs text-gray-500">
            The video will be uploaded to YouTube immediately with the selected privacy setting.
          </p>
        )}

        {uploadMode === 'scheduled' && (
          <div className="space-y-3 border-t pt-4">
            <p className="text-sm text-gray-700">
              The video will be uploaded now but published automatically by YouTube at the scheduled time.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Publish Date <span className="text-red-500">*</span>
                </label>
                <input
                  type="date"
                  value={scheduledDate}
                  onChange={e => setScheduledDate(e.target.value)}
                  min={new Date().toISOString().split('T')[0]}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Publish Time <span className="text-red-500">*</span>
                </label>
                <input
                  type="time"
                  value={scheduledTime}
                  onChange={e => setScheduledTime(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Timezone</label>
              <input
                type="text"
                value={scheduledTimezone}
                onChange={e => setScheduledTimezone(e.target.value)}
                placeholder="e.g. Asia/Kolkata, America/New_York"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
              />
              <p className="text-xs text-gray-400 mt-1">
                Default: {defaultTimezone}. Use IANA timezone names.
              </p>
            </div>

            <div className="bg-blue-50 border border-blue-200 text-blue-800 text-xs rounded-lg p-2.5 space-y-1">
              <p className="font-medium">How scheduling works:</p>
              <ul className="list-disc list-inside space-y-0.5">
                <li>The video file is uploaded to YouTube right now</li>
                <li>YouTube handles the actual publishing at the scheduled time</li>
                <li>The local video file is deleted after confirmed upload</li>
                <li>You can reschedule or cancel from the upload history</li>
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Submit button */}
      <div className="space-y-3 pb-8">
        <button
          type="button"
          onClick={() => handleAction(uploadMode)}
          disabled={submitting || !isConnected || !title.trim()}
          className={`w-full py-3 font-semibold rounded-lg transition text-white ${
            uploadMode === 'scheduled'
              ? 'bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300'
              : 'bg-red-600 hover:bg-red-700 disabled:bg-gray-300'
          }`}
        >
          {submitting
            ? 'Queuing…'
            : uploadMode === 'scheduled'
            ? '📅 Schedule Short'
            : '▶ Upload to YouTube'}
        </button>

        {!isConnected && (
          <p className="text-xs text-center text-gray-500">
            <Link to="/youtube/connect" className="text-indigo-600 underline">Connect YouTube</Link>{' '}
            to enable uploading.
          </p>
        )}
      </div>
    </div>
  )
}
