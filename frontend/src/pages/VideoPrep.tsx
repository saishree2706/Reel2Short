/**
 * VideoPrep — video preparation / conversion page.
 *
 * Flow:
 * - Vertical/Square → "Ready" message, Continue button.
 * - Horizontal → Mode picker (Center Crop | Blur Background), Generate, then
 *   poll job status and show preview when done.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { Spinner } from '../components/Spinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { AspectRatioBadge } from '../components/AspectRatioBadge';
import api from '../services/api';

type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';

interface Job {
  id: string;
  status: JobStatus;
  conversion_mode: string;
  output_asset_id: string | null;
  error_message: string | null;
  progress: number | null;
}

interface VideoAsset {
  id: string;
  original_filename: string;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  aspect_ratio: string | null;
  file_size: number | null;
  source: string;
  conversion_mode: string | null;
}

const POLL_INTERVAL_MS = 2500;

export default function VideoPrep() {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();

  const [asset, setAsset] = useState<VideoAsset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Probe state
  const [probing, setProbing] = useState(false);
  const [probed, setProbed] = useState(false);

  // Conversion state
  const [mode, setMode] = useState<'crop' | 'blur_background' | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [outputAsset, setOutputAsset] = useState<VideoAsset | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load asset and auto-probe
  useEffect(() => {
    if (!assetId) return;
    loadAsset();
  }, [assetId]);

  async function loadAsset() {
    try {
      setLoading(true);
      setError(null);
      const resp = await api.get(`/videos/${assetId}`);
      setAsset(resp.data);

      // Auto-probe if we don't have dimensions yet
      if (!resp.data.width || !resp.data.aspect_ratio || resp.data.aspect_ratio === 'unknown') {
        await runProbe();
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load video.');
    } finally {
      setLoading(false);
    }
  }

  async function runProbe() {
    try {
      setProbing(true);
      const resp = await api.get(`/videos/${assetId}/probe`);
      setAsset(prev => prev ? { ...prev, ...resp.data, id: prev.id } : prev);
      setProbed(true);
    } catch (e: any) {
      // Non-fatal — ffprobe may not be available
      console.warn('Probe failed:', e);
    } finally {
      setProbing(false);
    }
  }

  async function startConversion() {
    if (!mode || !assetId) return;
    try {
      setSubmitting(true);
      setError(null);
      const resp = await api.post(`/videos/${assetId}/convert`, { mode });
      setJob(resp.data);
      startPolling(resp.data.id);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create conversion job.');
    } finally {
      setSubmitting(false);
    }
  }

  function startPolling(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const resp = await api.get(`/jobs/${jobId}`);
        const j: Job = resp.data;
        setJob(j);
        if (j.status === 'completed' || j.status === 'failed') {
          clearInterval(pollRef.current!);
          if (j.status === 'completed' && j.output_asset_id) {
            const out = await api.get(`/videos/${j.output_asset_id}`);
            setOutputAsset(out.data);
          }
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, POLL_INTERVAL_MS);
  }

  // Cleanup polling on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  if (loading) return <div className="flex justify-center items-center h-64"><Spinner /></div>;
  if (error && !asset) return <ErrorAlert message={error} />;
  if (!asset) return null;

  const aspectRatio = asset.aspect_ratio || 'unknown';
  const isReady = aspectRatio === 'vertical' || aspectRatio === 'square';
  const needsConversion = aspectRatio === 'horizontal';
  const isUnknown = aspectRatio === 'unknown';

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold text-gray-900">Prepare Video</h1>
        <AspectRatioBadge ratio={aspectRatio} />
      </div>

      {/* Asset info */}
      <div className="bg-white rounded-lg shadow p-5 space-y-2 text-sm text-gray-600">
        <p><span className="font-medium text-gray-900">File:</span> {asset.original_filename}</p>
        {asset.width && asset.height && (
          <p><span className="font-medium text-gray-900">Dimensions:</span> {asset.width} × {asset.height}</p>
        )}
        {asset.duration_seconds && (
          <p><span className="font-medium text-gray-900">Duration:</span> {asset.duration_seconds.toFixed(1)}s</p>
        )}
        {asset.file_size && (
          <p><span className="font-medium text-gray-900">Size:</span> {(asset.file_size / 1024 / 1024).toFixed(1)} MB</p>
        )}
        {probing && <p className="text-indigo-600 flex items-center gap-2"><Spinner /> Probing video metadata…</p>}
      </div>

      {/* Video preview (original) */}
      <div className="bg-black rounded-lg overflow-hidden">
        <video
          key={asset.id}
          controls
          className="w-full max-h-80 object-contain"
          preload="metadata"
        >
          <source src={`/api/videos/${asset.id}/preview`} type="video/mp4" />
          Your browser does not support video playback.
        </video>
      </div>

      {error && <ErrorAlert message={error} />}

      {/* ---- VERTICAL / SQUARE: already ready ---- */}
      {isReady && !outputAsset && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-5 space-y-3">
          <div className="flex items-center gap-2 text-green-700 font-semibold text-lg">
            <span>✓</span>
            <span>{aspectRatio === 'vertical' ? 'Vertical' : 'Square'} — No conversion needed</span>
          </div>
          <p className="text-green-600 text-sm">
            This video is already in a suitable format for YouTube Shorts.
          </p>
          <button
            onClick={() => navigate('/videos')}
            className="bg-green-600 hover:bg-green-700 text-white font-medium px-6 py-2 rounded-lg transition"
          >
            Continue →
          </button>
        </div>
      )}

      {/* ---- UNKNOWN: probe button ---- */}
      {isUnknown && !needsConversion && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-5 space-y-3">
          <p className="text-yellow-800 font-medium">Could not detect video dimensions automatically.</p>
          <button
            onClick={runProbe}
            disabled={probing}
            className="bg-yellow-600 hover:bg-yellow-700 text-white font-medium px-5 py-2 rounded-lg disabled:opacity-50"
          >
            {probing ? 'Probing…' : 'Re-probe with ffprobe'}
          </button>
        </div>
      )}

      {/* ---- HORIZONTAL: conversion picker ---- */}
      {needsConversion && !job && (
        <div className="bg-white rounded-lg shadow p-5 space-y-5">
          <p className="font-semibold text-gray-900">This is a horizontal video. Choose a format:</p>

          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setMode('crop')}
              className={`p-4 rounded-lg border-2 text-left transition ${
                mode === 'crop'
                  ? 'border-indigo-600 bg-indigo-50'
                  : 'border-gray-200 hover:border-gray-400'
              }`}
            >
              <p className="font-semibold text-gray-900 mb-1">Center Crop</p>
              <p className="text-sm text-gray-500">
                Crops the center of the video to 9:16 (1080×1920). Parts of the frame are cut off.
              </p>
            </button>

            <button
              onClick={() => setMode('blur_background')}
              className={`p-4 rounded-lg border-2 text-left transition ${
                mode === 'blur_background'
                  ? 'border-indigo-600 bg-indigo-50'
                  : 'border-gray-200 hover:border-gray-400'
              }`}
            >
              <p className="font-semibold text-gray-900 mb-1">Blur Background</p>
              <p className="text-sm text-gray-500">
                Preserves the full video over a blurred background to fill 9:16 (1080×1920).
              </p>
            </button>
          </div>

          <button
            onClick={startConversion}
            disabled={!mode || submitting}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white font-semibold py-3 rounded-lg transition"
          >
            {submitting ? 'Submitting…' : 'Generate'}
          </button>
        </div>
      )}

      {/* ---- JOB STATUS ---- */}
      {job && job.status !== 'completed' && (
        <div className="bg-white rounded-lg shadow p-5 space-y-3">
          <p className="font-semibold text-gray-900">Processing…</p>
          <div className="flex items-center gap-3">
            <JobStatusBadge status={job.status} />
            {(job.status === 'queued' || job.status === 'processing') && <Spinner />}
          </div>
          {job.status === 'queued' && (
            <p className="text-sm text-gray-500">Job is queued. The worker will pick it up shortly.</p>
          )}
          {job.status === 'processing' && (
            <p className="text-sm text-gray-500">FFmpeg is converting your video. This may take a minute.</p>
          )}
          {job.status === 'failed' && (
            <>
              <ErrorAlert message={job.error_message || 'Conversion failed.'} />
              <button
                onClick={() => { setJob(null); setMode(null); }}
                className="bg-red-600 hover:bg-red-700 text-white font-medium px-5 py-2 rounded-lg"
              >
                Retry
              </button>
            </>
          )}
        </div>
      )}

      {/* ---- COMPLETED: show converted preview ---- */}
      {job?.status === 'completed' && outputAsset && (
        <div className="bg-white rounded-lg shadow p-5 space-y-4">
          <div className="flex items-center gap-2 text-green-700 font-semibold text-lg">
            <span>✓</span><span>Conversion complete!</span>
          </div>
          <div className="bg-black rounded-lg overflow-hidden">
            <video
              key={outputAsset.id}
              controls
              autoPlay={false}
              className="w-full max-h-96 object-contain"
            >
              <source src={`/api/videos/${outputAsset.id}/preview`} type="video/mp4" />
            </video>
          </div>
          {outputAsset.width && outputAsset.height && (
            <p className="text-sm text-gray-500">
              Output: {outputAsset.width} × {outputAsset.height}
              {outputAsset.duration_seconds && ` · ${outputAsset.duration_seconds.toFixed(1)}s`}
            </p>
          )}
          <button
            onClick={() => navigate('/videos')}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-6 py-2 rounded-lg transition"
          >
            Continue →
          </button>
        </div>
      )}
    </div>
  );
}

function JobStatusBadge({ status }: { status: JobStatus }) {
  const colors: Record<JobStatus, string> = {
    queued: 'bg-yellow-100 text-yellow-800',
    processing: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${colors[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
