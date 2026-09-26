"""Tests for FFmpeg service: binary detection, probing, aspect ratio, commands."""
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

class TestBinaryDetection:

    def test_verify_binaries_success(self):
        """Both ffmpeg and ffprobe on PATH → verify_binaries returns paths."""
        from app.services.ffmpeg_service import verify_binaries
        result = verify_binaries()
        assert "ffmpeg" in result
        assert "ffprobe" in result
        assert result["ffmpeg"]
        assert result["ffprobe"]

    def test_verify_binaries_missing_ffmpeg(self):
        """Missing ffmpeg binary raises RuntimeError with clear message."""
        from app.services.ffmpeg_service import verify_binaries
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with pytest.raises(RuntimeError, match="ffmpeg"):
                    verify_binaries()

    def test_custom_path_override(self, tmp_path):
        """FFMPEG_PATH pointing to non-existent path raises RuntimeError."""
        from app.config import _resolve_binary
        fake_path = str(tmp_path / "ffmpeg_fake.exe")
        # Make shutil.which return None so only the explicit path is checked
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="ffmpeg"):
                _resolve_binary("ffmpeg", fake_path)

    def test_ffprobe_path_found_via_which(self):
        """ffprobe discovered via PATH."""
        import shutil
        result = shutil.which("ffprobe")
        assert result is not None, "ffprobe must be on PATH for this test"


# ---------------------------------------------------------------------------
# Aspect ratio classification
# ---------------------------------------------------------------------------

class TestAspectRatioClassification:

    def test_vertical_9_16(self):
        from app.services.ffmpeg_service import classify_aspect_ratio
        assert classify_aspect_ratio(1080, 1920) == "vertical"

    def test_horizontal_16_9(self):
        from app.services.ffmpeg_service import classify_aspect_ratio
        assert classify_aspect_ratio(1920, 1080) == "horizontal"

    def test_square(self):
        from app.services.ffmpeg_service import classify_aspect_ratio
        assert classify_aspect_ratio(1080, 1080) == "square"

    def test_near_square_within_tolerance(self):
        from app.services.ffmpeg_service import classify_aspect_ratio
        # ratio = 1040/1000 = 1.04 — clearly within 5% tolerance
        assert classify_aspect_ratio(1040, 1000) == "square"
        # ratio = 960/1000 = 0.96 — clearly within 5% tolerance (vertical side)
        assert classify_aspect_ratio(960, 1000) == "square"

    def test_unknown_when_none(self):
        from app.services.ffmpeg_service import classify_aspect_ratio
        assert classify_aspect_ratio(None, None) == "unknown"
        assert classify_aspect_ratio(0, 1080) == "unknown"

    def test_slightly_horizontal(self):
        from app.services.ffmpeg_service import classify_aspect_ratio
        # ratio = 1200/1000 = 1.2 → horizontal
        assert classify_aspect_ratio(1200, 1000) == "horizontal"


# ---------------------------------------------------------------------------
# Video probing
# ---------------------------------------------------------------------------

class TestVideoProbing:

    @pytest.mark.asyncio
    async def test_probe_real_video(self, sample_video):
        """Integration test: probe the real instagram_reel.mp4."""
        from app.services.ffmpeg_service import probe_video
        result = await probe_video(sample_video)
        assert result["width"] is not None
        assert result["height"] is not None
        assert result["duration_seconds"] is not None and result["duration_seconds"] > 0
        assert result["aspect_ratio"] in ("vertical", "square", "horizontal", "unknown")

    @pytest.mark.asyncio
    async def test_probe_missing_file(self, tmp_path):
        """Probing a non-existent file returns empty dict gracefully."""
        from app.services.ffmpeg_service import probe_video
        result = await probe_video(tmp_path / "nonexistent.mp4")
        assert result["width"] is None
        assert result["height"] is None
        assert result["aspect_ratio"] == "unknown"

    @pytest.mark.asyncio
    async def test_probe_invalid_file(self, tmp_path):
        """Probing a non-video file returns empty dict gracefully."""
        from app.services.ffmpeg_service import probe_video
        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"this is not a video")
        result = await probe_video(bad)
        # Should not raise; may return None values
        assert isinstance(result, dict)
        assert "aspect_ratio" in result

    def test_probe_sync_real_video(self, sample_video):
        """Synchronous probe works on real video."""
        from app.services.ffmpeg_service import probe_video_sync
        result = probe_video_sync(sample_video)
        assert result["width"] is not None

    @pytest.mark.asyncio
    async def test_probe_extracts_fps(self, sample_video):
        """Probe extracts FPS for a real video."""
        from app.services.ffmpeg_service import probe_video
        result = await probe_video(sample_video)
        # fps may be None for synthetic videos, but should be > 0 for real ones
        if result["fps"] is not None:
            assert result["fps"] > 0


# ---------------------------------------------------------------------------
# FFmpeg command builders
# ---------------------------------------------------------------------------

class TestCommandBuilders:

    def test_crop_cmd_structure(self, tmp_path):
        from app.services.ffmpeg_service import build_crop_cmd
        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        cmd = build_crop_cmd(inp, out, "ffmpeg")
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert str(inp) in cmd
        assert str(out) in cmd
        # Contains crop filter
        assert any("crop" in arg for arg in cmd)

    def test_blur_cmd_structure(self, tmp_path):
        from app.services.ffmpeg_service import build_blur_cmd
        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        cmd = build_blur_cmd(inp, out, "ffmpeg")
        assert cmd[0] == "ffmpeg"
        assert "-filter_complex" in cmd
        assert any("boxblur" in arg for arg in cmd)
        assert any("overlay" in arg for arg in cmd)

    def test_run_ffmpeg_sync_bad_binary(self):
        from app.services.ffmpeg_service import run_ffmpeg_sync
        returncode, stderr = run_ffmpeg_sync(["totally_fake_binary_xyz", "-v"])
        assert returncode != 0


# ---------------------------------------------------------------------------
# Real FFmpeg conversion integration test
# ---------------------------------------------------------------------------

class TestFFmpegConversion:

    def test_crop_conversion_real_video(self, sample_video, tmp_path):
        """Run actual FFmpeg crop conversion on the real video (slow test)."""
        from app.services.ffmpeg_service import (
            build_crop_cmd, run_ffmpeg_sync, get_ffmpeg, probe_video_sync
        )
        ffmpeg = get_ffmpeg()
        output = tmp_path / "cropped.mp4"
        cmd = build_crop_cmd(sample_video, output, ffmpeg)
        code, stderr = run_ffmpeg_sync(cmd)
        assert code == 0, f"FFmpeg failed: {stderr[-300:]}"
        assert output.exists()
        assert output.stat().st_size > 0
        probe = probe_video_sync(output)
        assert probe["width"] == 1080
        assert probe["height"] == 1920

    def test_blur_conversion_real_video(self, sample_video, tmp_path):
        """Run actual FFmpeg blur-background conversion."""
        from app.services.ffmpeg_service import (
            build_blur_cmd, run_ffmpeg_sync, get_ffmpeg, probe_video_sync
        )
        ffmpeg = get_ffmpeg()
        output = tmp_path / "blurred.mp4"
        cmd = build_blur_cmd(sample_video, output, ffmpeg)
        code, stderr = run_ffmpeg_sync(cmd)
        assert code == 0, f"FFmpeg failed: {stderr[-300:]}"
        assert output.exists()
        probe = probe_video_sync(output)
        assert probe["width"] == 1080
        assert probe["height"] == 1920
