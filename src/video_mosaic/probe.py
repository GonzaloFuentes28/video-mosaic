"""Video probing via ffprobe."""

import json
import os
import subprocess

from . import VideoMosaicError

SUBPROCESS_TIMEOUT = 30


def get_video_info(video_path: str) -> dict:
    """Get video duration, fps, resolution, and filename using ffprobe.

    Raises:
        VideoMosaicError: If ffprobe is not found or the file cannot be probed.
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=SUBPROCESS_TIMEOUT)
    except FileNotFoundError:
        raise VideoMosaicError("ffmpeg/ffprobe not found. Install ffmpeg first.")
    except subprocess.CalledProcessError:
        raise VideoMosaicError(f"ffprobe failed to read '{video_path}'. Is it a valid video file?")
    except subprocess.TimeoutExpired:
        raise VideoMosaicError(f"ffprobe timed out reading '{video_path}'.")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise VideoMosaicError("Failed to parse ffprobe output.")

    try:
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        raise VideoMosaicError("Could not determine video duration. Is it a valid video file?")

    filename = os.path.basename(data.get("format", {}).get("filename", video_path))

    # Find the first video stream
    fps = 30.0
    width, height = 0, 0
    found_video = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            found_video = True
            try:
                num, den = map(int, stream["r_frame_rate"].split("/"))
                fps = num / den if den else 30.0
                if fps <= 0:
                    fps = 30.0
            except (KeyError, ValueError, ZeroDivisionError):
                fps = 30.0
            try:
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
            except (TypeError, ValueError):
                width, height = 0, 0
            break

    if not found_video:
        raise VideoMosaicError("No video stream found in file.")

    if width == 0 or height == 0:
        raise VideoMosaicError("Could not determine video resolution.")

    return {
        "duration": duration,
        "fps": fps,
        "width": width,
        "height": height,
        "filename": filename,
    }
