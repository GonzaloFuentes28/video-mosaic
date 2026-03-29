"""Download videos from URLs using yt-dlp."""

import os
import re
import subprocess
import threading
from collections.abc import Callable
from urllib.parse import urlparse

from . import VideoMosaicError

SUBPROCESS_TIMEOUT = 600  # 10 minutes


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
    """Download a video from a URL using yt-dlp (CLI).

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

    cmd = [
        "yt-dlp", "--no-playlist", "--newline",
        "--merge-output-format", "mp4",
        "-o", output_path,
    ]

    if quality is not None:
        cmd += ["-f", f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"]
    else:
        cmd += ["-f", "bestvideo+bestaudio/best"]

    cmd += ["--", url]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        raise VideoMosaicError(
            "yt-dlp is required for URL downloads. Install it with:\n"
            "  pip install yt-dlp\n"
            "  brew install yt-dlp"
        )

    # Parse progress from yt-dlp output (e.g. "[download]  45.2% of 3.50MiB")
    pct_re = re.compile(r"\[download\]\s+([\d.]+)%")

    def _read_output() -> None:
        for line in proc.stdout:
            if on_progress:
                m = pct_re.search(line)
                if m:
                    on_progress(float(m.group(1)))

    reader = threading.Thread(target=_read_output, daemon=True)
    reader.start()
    proc.wait(timeout=SUBPROCESS_TIMEOUT)
    reader.join(timeout=5)

    if proc.returncode != 0:
        raise VideoMosaicError(f"yt-dlp failed to download '{url}'.")

    if not os.path.isfile(output_path):
        raise VideoMosaicError("Download finished but no video file was produced.")
