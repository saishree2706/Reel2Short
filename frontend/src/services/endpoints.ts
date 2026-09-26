import api from './api'
import type {
  HealthResponse,
  InstagramMediaList,
  ProbeResponse,
  ReelStatusResponse,
  VideoAsset,
  VideoAssetList,
} from '../types'

// ------- Health -------
export const getHealth = () =>
  api.get<HealthResponse>('/health').then((r) => r.data)

// ------- Instagram -------
export const getReels = (cursor?: string, limit = 25) =>
  api
    .get<InstagramMediaList>('/instagram/reels', {
      params: { cursor, limit },
    })
    .then((r) => r.data)

export const getReelStatus = (mediaId: string) =>
  api
    .get<ReelStatusResponse>(`/instagram/reels/${mediaId}/status`)
    .then((r) => r.data)

// ------- Videos -------
export const downloadReel = (params: {
  media_id: string
  media_url: string
  caption?: string | null
  permalink?: string | null
  instagram_timestamp?: string | null
  thumbnail_url?: string | null
}) => {
  const form = new FormData()
  Object.entries(params).forEach(([k, v]) => {
    if (v != null) form.append(k, v)
  })
  return api.post<VideoAsset>('/videos/download', form).then((r) => r.data)
}

export const uploadVideo = (
  file: File,
  meta?: {
    source_media_id?: string
    caption?: string
    permalink?: string
    instagram_timestamp?: string
    thumbnail_url?: string
  }
) => {
  const form = new FormData()
  form.append('file', file)
  if (meta) {
    Object.entries(meta).forEach(([k, v]) => {
      if (v != null) form.append(k, v)
    })
  }
  return api.post<VideoAsset>('/videos/upload', form).then((r) => r.data)
}

export const getVideos = (skip = 0, limit = 50) =>
  api
    .get<VideoAssetList>('/videos', { params: { skip, limit } })
    .then((r) => r.data)

export const getVideo = (id: string) =>
  api.get<VideoAsset>(`/videos/${id}`).then((r) => r.data)

export const deleteVideo = (id: string) =>
  api.delete(`/videos/${id}`)

export const videoFileUrl = (id: string) => `/api/videos/${id}/file`

export const probeVideo = (id: string) =>
  api.get<ProbeResponse>(`/videos/${id}/probe`).then((r) => r.data)

