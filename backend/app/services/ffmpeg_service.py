"""
FFmpeg/ffprobe service.

All FFmpeg-specific logic lives here. API routes and workers call this module.
"""
import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def get_ffmpeg() -> str:
    """Return resolved ffmpeg path or raise RuntimeError."""
    return settings.resolve_ffmpeg()


def get_ffprobe() -> str:
    """Return resolved ffprobe path or raise RuntimeError."""
    return settings.resolve_ffprobe()


def verify_binaries() -> dict[str, str]:
    """
    Verify both ffmpeg and ffprobe are usable.
    Returns {'ffmpeg': path, 'ffprobe': path}.
    Raises RuntimeError with a clear message if either is missing.
    """
    ffmpeg = get_ffmpeg()
    ffprobe = get_ffprobe()

    # Quick smoke-test: ask for version
    for binary, name in [(ffmpeg, "ffmpeg"), (ffprobe, "ffprobe")]:
        try:
            result = subprocess.run(
                [binary, "-version"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"'{name}' at '{binary}' returned non-zero exit code. "
                    "Check your installation."
                )
        except FileNotFoundError:
            raise RuntimeError(
                f"'{name}' binary not found at '{binary}'. "
                f"Install FFmpeg and add it to PATH, or set {name.upper()}_PATH in .env."
            )

    return {"ffmpeg": ffmpeg, "ffprobe": ffprobe}


# ---------------------------------------------------------------------------
# Video probing
# ---------------------------------------------------------------------------

async def probe_video(file_path: Path) -> dict:
    """
    Run ffprobe on *file_path* and return structured metadata.

    Returns a dict with keys:
        width, height, duration_seconds, codec_name, fps, has_audio,
        format_name, aspect_ratio, file_size

    All values may be None if not detectable or if ffprobe is unavailable.
    aspect_ratio is one of: 'vertical', 'square', 'horizontal', 'unknown'.
    """
    return await asyncio.to_thread(probe_video_sync, file_path)


def probe_video_sync(file_path: Path) -> dict:
    """Synchronous version of probe_video for use in workers and background threads."""
    try:
        ffprobe = get_ffprobe()
    except RuntimeError as e:
        logger.warning("ffprobe resolution failed: %s", e)
        return _empty_probe(file_path)

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(file_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            logger.warning(
                "ffprobe exited with code %d on %s: %s",
                result.returncode,
                file_path.name,
                result.stderr.decode("utf-8", errors="replace"),
            )
            return _empty_probe(file_path)
        raw = json.loads(result.stdout.decode("utf-8", errors="replace"))
    except Exception as e:
        logger.warning("Exception during ffprobe on %s: %s", file_path.name, e)
        return _empty_probe(file_path)

    return _parse_probe(raw, file_path)


def _parse_probe(raw: dict, file_path: Path) -> dict:
    width = height = duration = codec = fps = fmt_name = None
    has_audio = False

    for stream in raw.get("streams", []):
        if stream.get("codec_type") == "video" and width is None:
            width = stream.get("width")
            height = stream.get("height")
            codec = stream.get("codec_name")

            # FPS: prefer avg_frame_rate
            for fps_key in ("avg_frame_rate", "r_frame_rate"):
                fps_str = stream.get(fps_key, "")
                if fps_str and "/" in fps_str:
                    num, den = fps_str.split("/", 1)
                    try:
                        fps_val = float(num) / float(den)
                        if fps_val > 0:
                            fps = round(fps_val, 3)
                            break
                    except (ValueError, ZeroDivisionError):
                        pass

            try:
                duration = float(stream.get("duration", 0)) or None
            except (TypeError, ValueError):
                pass

        elif stream.get("codec_type") == "audio":
            has_audio = True

    fmt_info = raw.get("format", {})
    if not duration:
        try:
            duration = float(fmt_info.get("duration", 0)) or None
        except (TypeError, ValueError):
            pass
    fmt_name = fmt_info.get("format_name")

    aspect = classify_aspect_ratio(width, height)

    file_size = None
    try:
        file_size = file_path.stat().st_size
    except OSError:
        pass

    return {
        "width": width,
        "height": height,
        "duration_seconds": duration,
        "codec_name": codec,
        "fps": fps,
        "has_audio": has_audio,
        "format_name": fmt_name,
        "aspect_ratio": aspect,
        "file_size": file_size,
    }


def _empty_probe(file_path: Path) -> dict:
    file_size = None
    try:
        file_size = file_path.stat().st_size
    except OSError:
        pass
    return {
        "width": None,
        "height": None,
        "duration_seconds": None,
        "codec_name": None,
        "fps": None,
        "has_audio": None,
        "format_name": None,
        "aspect_ratio": "unknown",
        "file_size": file_size,
    }


# ---------------------------------------------------------------------------
# Aspect ratio classification
# ---------------------------------------------------------------------------

def classify_aspect_ratio(
    width: Optional[int], height: Optional[int], tolerance: float = 0.05
) -> str:
    """
    Classify aspect ratio with tolerance.

    vertical   → ratio < (1 - tolerance)     e.g. 9:16
    square     → ratio within ±tolerance of 1 e.g. 1:1
    horizontal → ratio > (1 + tolerance)     e.g. 16:9
    """
    if not width or not height or width <= 0 or height <= 0:
        return "unknown"
    ratio = width / height
    if abs(ratio - 1.0) <= tolerance:
        return "square"
    if ratio < 1.0:
        return "vertical"
    return "horizontal"


# ---------------------------------------------------------------------------
# FFmpeg conversion commands
# ---------------------------------------------------------------------------

TARGET_W, TARGET_H = 1080, 1920  # 9:16 vertical target


def build_crop_cmd(
    input_path: Path,
    output_path: Path,
    ffmpeg: str,
) -> list[str]:
    """
    Center-crop to 9:16 (1080×1920).

    Uses scale + crop filter. The video is first scaled so its height is
    1920, then the width is cropped to 1080 from center.
    """
    return [
        ffmpeg,
        "-y",
        "-i", str(input_path),
        "-vf", (
            f"scale=-2:{TARGET_H},"
            f"crop={TARGET_W}:{TARGET_H}"
        ),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]


def build_blur_cmd(
    input_path: Path,
    output_path: Path,
    ffmpeg: str,
) -> list[str]:
    """
    Blur-background mode: 9:16 canvas with blurred/scaled background,
    original video scaled to fit overlaid in the center.

    filtergraph:
    1. Split input into two streams.
    2. [bg]  scale to 1080×1920, boxblur.
    3. [fg]  scale to fit within 1080×1920 (no upscale).
    4. overlay fg centered on bg.
    """
    fg_scale = f"scale='min({TARGET_W},iw)':'min({TARGET_H},ih)':force_original_aspect_ratio=decrease"
    return [
        ffmpeg,
        "-y",
        "-i", str(input_path),
        "-filter_complex", (
            f"[0:v]split=2[bg_in][fg_in];"
            f"[bg_in]scale={TARGET_W}:{TARGET_H},boxblur=20:5[bg];"
            f"[fg_in]{fg_scale}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
        ),
        "-map", "[out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]


def run_ffmpeg_sync(cmd: list[str], timeout: int = 600) -> tuple[int, str]:
    """
    Run an FFmpeg command synchronously.
    Returns (returncode, stderr_text).
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
        )
        stderr = result.stderr.decode("utf-8", errors="replace")
        return result.returncode, stderr
    except subprocess.TimeoutExpired:
        return -1, "FFmpeg timed out after {timeout}s"
    except FileNotFoundError as e:
        return -1, str(e)
    except Exception as e:
        return -1, str(e)

