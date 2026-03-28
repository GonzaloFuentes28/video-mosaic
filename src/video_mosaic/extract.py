"""Frame extraction strategies using ffmpeg."""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from . import VideoMosaicError

SUBPROCESS_TIMEOUT = 300  # 5 minutes per ffmpeg call


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run an ffmpeg command with user-friendly error handling."""
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=SUBPROCESS_TIMEOUT)
    except FileNotFoundError:
        raise VideoMosaicError("ffmpeg not found. Install ffmpeg first.")
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() if e.stderr else "unknown error"
        raise VideoMosaicError(f"ffmpeg failed → {msg}")
    except subprocess.TimeoutExpired:
        raise VideoMosaicError("ffmpeg timed out.")


def _build_trim_args(start: float | None, end: float | None) -> list[str]:
    """Build ffmpeg -ss / -to args for trimming."""
    args: list[str] = []
    if start is not None:
        args += ["-ss", f"{start:.4f}"]
    if end is not None:
        args += ["-to", f"{end:.4f}"]
    return args


def extract_all_frames(
    video_path: str,
    tmp_dir: str,
    duration: float,
    start: float | None = None,
    end: float | None = None,
) -> list[tuple[Path, float]]:
    """Extract every single frame. Returns list of (path, timestamp_seconds)."""
    pattern = os.path.join(tmp_dir, "frame_%08d.jpg")
    trim = _build_trim_args(start, end)
    cmd = ["ffmpeg", "-v", "quiet"] + trim + ["-i", video_path, "-qscale:v", "3", pattern]
    _run_ffmpeg(cmd)

    paths = sorted(Path(tmp_dir).glob("frame_*.jpg"))
    base_offset = start if start is not None else 0.0
    trimmed_dur = (end if end is not None else duration) - base_offset
    dt = trimmed_dur / max(len(paths), 1)
    return [(p, base_offset + i * dt) for i, p in enumerate(paths)]


def extract_every_n_seconds(
    video_path: str,
    tmp_dir: str,
    interval: float,
    start: float | None = None,
    end: float | None = None,
) -> list[tuple[Path, float]]:
    """Extract one frame every *interval* seconds."""
    interval = float(interval)
    if interval <= 0:
        raise VideoMosaicError(f"Interval must be positive, got {interval}.")

    pattern = os.path.join(tmp_dir, "frame_%08d.jpg")
    trim = _build_trim_args(start, end)
    cmd = (
        ["ffmpeg", "-v", "quiet"]
        + trim
        + ["-i", video_path, "-vf", f"fps=1/{interval}", "-qscale:v", "3", pattern]
    )
    _run_ffmpeg(cmd)

    paths = sorted(Path(tmp_dir).glob("frame_*.jpg"))
    base_offset = start if start is not None else 0.0
    return [(p, base_offset + i * interval) for i, p in enumerate(paths)]


def extract_n_frames(
    video_path: str,
    tmp_dir: str,
    n: int,
    duration: float,
    start: float | None = None,
    end: float | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[tuple[Path, float]]:
    """Extract exactly *n* frames evenly distributed.

    Args:
        on_progress: Optional callback(current, total) called after each frame.
    """
    if n < 1:
        raise VideoMosaicError(f"Number of frames must be at least 1, got {n}.")

    t_start = start if start is not None else 0.0
    t_end = end if end is not None else duration

    if n == 1:
        timestamps = [t_start]
    else:
        timestamps = [t_start + i * (t_end - t_start) / (n - 1) for i in range(n)]
        timestamps[-1] = max(t_start, min(timestamps[-1], t_end - 0.01))

    result: list[tuple[Path, float]] = []
    for i, ts in enumerate(timestamps):
        out = os.path.join(tmp_dir, f"frame_{i:08d}.jpg")
        _run_ffmpeg(
            [
                "ffmpeg", "-v", "quiet",
                "-ss", f"{ts:.4f}",
                "-i", video_path,
                "-frames:v", "1",
                "-qscale:v", "3",
                out,
            ],
        )
        if os.path.exists(out):
            result.append((Path(out), ts))
        if on_progress:
            on_progress(i + 1, len(timestamps))

    return result
