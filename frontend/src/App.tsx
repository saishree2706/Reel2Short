import { Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { Dashboard } from './pages/Dashboard'
import { InstagramReels } from './pages/InstagramReels'
import { VideoDownload } from './pages/VideoDownload'
import { ManualUpload } from './pages/ManualUpload'
import { VideoList } from './pages/VideoList'
import { VideoDetail } from './pages/VideoDetail'
import VideoPrep from './pages/VideoPrep'
import YouTubeConnect from './pages/YouTubeConnect'
import YouTubeUpload from './pages/YouTubeUpload'
import UploadStatus from './pages/UploadStatus'
import UploadHistory from './pages/UploadHistory'

export default function App() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          {/* Stage 1 */}
          <Route path="/" element={<Dashboard />} />
          <Route path="/reels" element={<InstagramReels />} />
          <Route path="/reels/:mediaId/download" element={<VideoDownload />} />
          <Route path="/upload" element={<ManualUpload />} />
          <Route path="/videos" element={<VideoList />} />
          <Route path="/videos/:id" element={<VideoDetail />} />

          {/* Stage 2 */}
          <Route path="/videos/:assetId/prepare" element={<VideoPrep />} />

          {/* Stage 3 */}
          <Route path="/youtube/connect" element={<YouTubeConnect />} />
          <Route path="/videos/:assetId/youtube" element={<YouTubeUpload />} />
          <Route path="/youtube/upload/:uploadId/status" element={<UploadStatus />} />

          {/* Stage 4 */}
          <Route path="/youtube/history" element={<UploadHistory />} />
        </Routes>
      </main>
    </div>
  )
}
