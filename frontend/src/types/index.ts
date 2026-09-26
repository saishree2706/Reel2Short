/** Shared TypeScript types matching backend Pydantic schemas. */

// Instagram
export interface InstagramMedia {
  id: string
  media_type: string
  media_product_type: string | null
  media_url: string | null
  thumbnail_url: string | null
  permalink: string | null
  caption: string | null
  timestamp: string | null
}

export interface InstagramMediaList {
  items: InstagramMedia[]
  next_cursor: string | null
  has_more: boolean
}

export interface ReelStatusResponse {
  media_id: string
  download_available: boolean
  manual_upload_required: boolean
  media_url: string | null
  thumbnail_url: string | null
  caption: string | null
  timestamp: string | null
  permalink: string | null
}

// Videos
export interface VideoAsset {
  id: string
  source: string
  source_media_id: string | null
  source_url: string | null
  file_path: string
  original_filename: string
  mime_type: string | null
  file_size: number | null
  width: number | null
  height: number | null
  duration_seconds: number | null
  aspect_ratio: string | null
  caption: string | null
  permalink: string | null
  instagram_timestamp: string | null
  thumbnail_url: string | null
  created_at: string
  updated_at: string
}

export interface VideoAssetList {
  items: VideoAsset[]
  total: number
}

export interface ProbeResponse {
  asset_id: string
  width: number | null
  height: number | null
  duration_seconds: number | null
  codec_name: string | null
  fps: number | null
  has_audio: boolean | null
  format_name: string | null
  aspect_ratio: string
  file_size: number | null
}

// Health
export interface HealthResponse {
  status: string
  environment: string
  python_version: string
  platform: string
  storage_dir: string
  instagram_configured: boolean
}
