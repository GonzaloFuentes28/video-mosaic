"""Frame extraction strategies using ffmpeg."""

import os
import re
import subprocess
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _run_ffmpeg_with_progress(
    cmd: list[str],
    estimated_total: int,
    on_progress: Callable[[int, int], None],
) -> None:
    """Run ffmpeg with -progress pipe:1 and report frame progress via callback."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise VideoMosaicError("ffmpeg not found. Install ffmpeg first.")

    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("frame="):
                try:
                    frame_num = int(line.split("=", 1)[1])
                    on_progress(frame_num, estimated_total)
                except (ValueError, IndexError):
                    pass
        proc.wait(timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise VideoMosaicError("ffmpeg timed out.")

    if proc.returncode != 0:
        stderr_out = proc.stderr.read() if proc.stderr else ""
        msg = stderr_out.strip() if stderr_out else "unknown error"
        raise VideoMosaicError(f"ffmpeg failed → {msg}")


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
    on_progress: Callable[[int, int], None] | None = None,
    estimated_frames: int | None = None,
) -> list[tuple[Path, float]]:
    """Extract every single frame. Returns list of (path, timestamp_seconds)."""
    pattern = os.path.join(tmp_dir, "frame_%08d.jpg")
    trim = _build_trim_args(start, end)

    if on_progress and estimated_frames:
        cmd = (
            ["ffmpeg", "-v", "quiet"]
            + trim
            + ["-i", video_path, "-qscale:v", "3", "-progress", "pipe:1", pattern]
        )
        _run_ffmpeg_with_progress(cmd, estimated_frames, on_progress)
    else:
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
    on_progress: Callable[[int, int], None] | None = None,
    estimated_frames: int | None = None,
) -> list[tuple[Path, float]]:
    """Extract one frame every *interval* seconds."""
    interval = float(interval)
    if interval <= 0:
        raise VideoMosaicError(f"Interval must be positive, got {interval}.")

    pattern = os.path.join(tmp_dir, "frame_%08d.jpg")
    trim = _build_trim_args(start, end)

    if on_progress and estimated_frames:
        cmd = (
            ["ffmpeg", "-v", "quiet"]
            + trim
            + [
                "-i",
                video_path,
                "-vf",
                f"fps=1/{interval}",
                "-qscale:v",
                "3",
                "-progress",
                "pipe:1",
                pattern,
            ]
        )
        _run_ffmpeg_with_progress(cmd, estimated_frames, on_progress)
    else:
        cmd = (
            ["ffmpeg", "-v", "quiet"]
            + trim
            + ["-i", video_path, "-vf", f"fps=1/{interval}", "-qscale:v", "3", pattern]
        )
        _run_ffmpeg(cmd)

    paths = sorted(Path(tmp_dir).glob("frame_*.jpg"))
    base_offset = start if start is not None else 0.0
    return [(p, base_offset + i * interval) for i, p in enumerate(paths)]


def _extract_single_frame(
    video_path: str,
    tmp_dir: str,
    index: int,
    timestamp: float,
) -> tuple[int, Path, float] | None:
    """Extract one frame at a given timestamp. Returns (index, path, timestamp) or None.

    Silently returns None if ffmpeg fails for this frame (e.g. seeking past end of video).
    """
    out = os.path.join(tmp_dir, f"frame_{index:08d}.jpg")
    try:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-v",
                "quiet",
                "-ss",
                f"{timestamp:.4f}",
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-qscale:v",
                "3",
                out,
            ],
        )
    except VideoMosaicError:
        return None
    if os.path.exists(out):
        return (index, Path(out), timestamp)
    return None


def extract_n_frames(
    video_path: str,
    tmp_dir: str,
    n: int,
    duration: float,
    start: float | None = None,
    end: float | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[tuple[Path, float]]:
    """Extract exactly *n* frames evenly distributed (concurrent).

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

    max_workers = min(n, os.cpu_count() or 4, 8)
    results: list[tuple[int, Path, float]] = []
    completed = 0
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_extract_single_frame, video_path, tmp_dir, i, ts): i
            for i, ts in enumerate(timestamps)
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)
            with lock:
                completed += 1
                if on_progress:
                    on_progress(completed, len(timestamps))

    results.sort(key=lambda r: r[0])
    return [(path, ts) for _, path, ts in results]


def extract_scene_changes(
    video_path: str,
    tmp_dir: str,
    threshold: float = 0.3,
    start: float | None = None,
    end: float | None = None,
) -> list[tuple[Path, float]]:
    """Extract frames at scene change points using ffmpeg's scene detection filter.

    Args:
        threshold: Scene change sensitivity (0.0-1.0). Lower values detect more scenes.
    """
    if not 0.0 <= threshold <= 1.0:
        raise VideoMosaicError(f"Scene threshold must be between 0.0 and 1.0, got {threshold}.")

    pattern = os.path.join(tmp_dir, "frame_%08d.jpg")
    trim = _build_trim_args(start, end)

    vf = f"select='gt(scene\\,{threshold})',showinfo"
    cmd = (
        ["ffmpeg"]
        + trim
        + ["-i", video_path, "-vf", vf, "-vsync", "vfr", "-qscale:v", "3", pattern]
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except FileNotFoundError:
        raise VideoMosaicError("ffmpeg not found. Install ffmpeg first.")
    except subprocess.TimeoutExpired:
        raise VideoMosaicError("ffmpeg timed out during scene detection.")

    if result.returncode != 0:
        msg = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown error"
        raise VideoMosaicError(f"ffmpeg scene detection failed → {msg}")

    # Parse pts_time from showinfo output in stderr
    pts_re = re.compile(r"pts_time:\s*([\d.]+)")
    timestamps = [float(m.group(1)) for m in pts_re.finditer(result.stderr)]

    paths = sorted(Path(tmp_dir).glob("frame_*.jpg"))

    if len(paths) == len(timestamps):
        return list(zip(paths, timestamps))

    # Fallback: use available timestamps, pad with 0.0 for any extras
    return [(p, timestamps[i] if i < len(timestamps) else 0.0) for i, p in enumerate(paths)]
