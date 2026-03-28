"""Download videos from URLs using yt-dlp."""

import os
from collections.abc import Callable
from urllib.parse import urlparse

from . import VideoMosaicError


def is_url(value: str) -> bool:
    """Return True if the value looks like an http(s) URL."""
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except ValueError:
        return False


def download_video(
    url: str,
    output_path: str,
    quality: int | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> None:
    """Download a video from a URL using yt-dlp.

    Args:
        url: The video URL.
        output_path: Where to save the downloaded video.
        quality: Max video height in pixels (e.g. 720, 1080). None for best.
        on_progress: Optional callback(percent) called during download (0.0 to 100.0).

    Raises:
        VideoMosaicError: If yt-dlp is not installed or the download fails.
    """
    if quality is not None:
        quality = int(quality)
        if quality < 1:
            raise VideoMosaicError(f"Quality must be a positive integer, got {quality}.")

    try:
        import yt_dlp
    except ImportError:
        raise VideoMosaicError(
            "yt-dlp is required for URL downloads. Install it with:\n"
            "  pip install yt-dlp\n"
            "  brew install yt-dlp"
        )

    def _progress_hook(d: dict) -> None:
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                on_progress(downloaded / total * 100)

    if quality is not None:
        fmt = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
    else:
        fmt = "bestvideo+bestaudio/best"

    opts = {
        "format": fmt,
        "outtmpl": output_path,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise VideoMosaicError(f"yt-dlp failed to download '{url}'.")
    except Exception as e:
        raise VideoMosaicError(f"Download failed: {e}")

    if not os.path.isfile(output_path):
        raise VideoMosaicError("Download finished but no video file was produced.")
