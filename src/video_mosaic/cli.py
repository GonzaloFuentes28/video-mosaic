#!/usr/bin/env python3
"""
video-mosaic — Extract frames from a video and compose them into a single mosaic image.

Usage:
    video-mosaic input.mp4 -o mosaic.jpg --every 5s
    video-mosaic input.mp4 -o mosaic.jpg --frames 64
    video-mosaic input.mp4 -o mosaic.jpg --all
    video-mosaic input.mp4 -o mosaic.jpg --scenes

    # From a URL (YouTube, Twitter/X, TikTok, Instagram, etc.)
    video-mosaic "https://x.com/user/status/123" -o mosaic.jpg --frames 48
    video-mosaic "https://youtube.com/watch?v=abc" --every 10s --quality 720

    # Trim, filter, reverse
    video-mosaic input.mp4 --frames 48 --from 1:00 --to 2:30
    video-mosaic input.mp4 --frames 48 --skip-black --skip-dupes
    video-mosaic input.mp4 --frames 48 --reverse

    # Scene change detection
    video-mosaic input.mp4 --scenes --scene-threshold 0.2

    # Batch mode (multiple inputs)
    video-mosaic *.mp4 --frames 24
    video-mosaic a.mp4 b.mp4 --frames 24 -o output_dir/

    # Export as PDF storyboard
    video-mosaic input.mp4 --frames 24 --pdf storyboard.pdf
"""

import argparse
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NoReturn

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TextColumn,
)
from rich.text import Text
from rich.theme import Theme

from . import VideoMosaicError
from .download import download_video, is_url
from .extract import (
    extract_all_frames,
    extract_every_n_seconds,
    extract_n_frames,
    extract_scene_changes,
)
from .filters import filter_frames
from .mosaic import MAX_CANVAS_PIXELS, compose_mosaic
from .pdf import export_pdf
from .probe import get_video_info
from .utils import fmt_timestamp, parse_interval, parse_timestamp

theme = Theme(
    {
        "info": "dim cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "label": "bold",
        "dim": "dim",
    }
)
console = Console(theme=theme, highlight=False)


class _CheckColumn(ProgressColumn):
    """Shows a spinner while running, ✓ when finished."""

    def __init__(self) -> None:
        super().__init__()
        self._spinner = SpinnerColumn("dots")

    def render(self, task: Task) -> Text:
        if task.finished:
            return Text("✓", style="bold green")
        return self._spinner.render(task)


def _make_progress(*extra_columns: ProgressColumn) -> Progress:
    """Create a Progress bar with consistent styling."""
    return Progress(
        _CheckColumn(),
        TextColumn("{task.description}"),
        *extra_columns,
        console=console,
    )


def _error(msg: str) -> NoReturn:
    """Print error and exit."""
    console.print(f"[error]Error:[/error] {msg}")
    sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-mosaic",
        description="Extract frames from a video and arrange them into a mosaic image.",
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="Path(s) to video file(s) or URL(s) (YouTube, Twitter/X, TikTok, etc.).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="mosaic.jpg",
        help="Output image path (default: mosaic.jpg). Supports .jpg, .png, .webp",
    )

    # Frame selection — mutually exclusive
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--all", action="store_true", help="Extract every frame (warning: can be huge)."
    )
    mode.add_argument(
        "--every", metavar="INTERVAL", help="One frame every INTERVAL (e.g. 5s, 500ms)."
    )
    mode.add_argument("--frames", type=int, metavar="N", help="Exactly N evenly-spaced frames.")
    mode.add_argument(
        "--scenes",
        action="store_true",
        help="Extract frames at scene changes (cuts/transitions).",
    )

    # Trim
    parser.add_argument(
        "--from", dest="trim_start", metavar="TIME", help="Start time (e.g. 1:30, 90, 0:05.5)."
    )
    parser.add_argument("--to", dest="trim_end", metavar="TIME", help="End time (e.g. 2:30, 150).")

    # Scene detection options
    parser.add_argument(
        "--scene-threshold",
        type=float,
        default=0.3,
        metavar="FLOAT",
        help="Scene detection sensitivity 0.0-1.0 (default: 0.3, lower=more scenes).",
    )

    # Filtering
    parser.add_argument("--skip-black", action="store_true", help="Exclude mostly-black frames.")
    parser.add_argument(
        "--skip-dupes", action="store_true", help="Exclude near-duplicate consecutive frames."
    )

    # Layout options
    parser.add_argument("--cols", type=int, default=None, help="Number of columns (default: auto).")
    parser.add_argument(
        "--thumb-width", type=int, default=None, help="Thumbnail width in px (default: native)."
    )
    parser.add_argument(
        "--padding", type=int, default=2, help="Padding between frames in px (default: 2)."
    )
    parser.add_argument("--bg", default="#1a1a1a", help="Background color (default: #1a1a1a).")
    parser.add_argument(
        "--labels", action="store_true", help="Show frame number + timestamp under each thumbnail."
    )
    parser.add_argument(
        "--no-header", action="store_true", help="Don't render video info header on the mosaic."
    )
    parser.add_argument(
        "--reverse", action="store_true", help="Reverse frame order (last frame first)."
    )

    # PDF export
    parser.add_argument("--pdf", metavar="PATH", help="Also export as a multi-page PDF storyboard.")

    # URL options
    parser.add_argument(
        "--quality",
        type=int,
        metavar="PX",
        help="Max video height for URL downloads (e.g. 720, 1080).",
    )

    # Misc
    parser.add_argument("--open", action="store_true", help="Open the output image after saving.")
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bar.")

    return parser


def _open_file(path: str) -> None:
    """Open a file with the OS default viewer."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", path])
        elif system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        pass


def _resolve_output_path(input_path: str, output_arg: str, batch: bool) -> str:
    """Resolve output path for a single video. Auto-names in batch mode."""
    if not batch:
        return output_arg

    stem = Path(input_path).stem
    ext = Path(output_arg).suffix or ".jpg"

    if os.path.isdir(output_arg):
        return os.path.join(output_arg, f"{stem}_mosaic{ext}")
    return f"{stem}_mosaic{ext}"


def _resolve_pdf_path(input_path: str, pdf_arg: str | None, batch: bool) -> str | None:
    """Resolve PDF output path for a single video."""
    if pdf_arg is None:
        return None
    if not batch:
        return pdf_arg

    stem = Path(input_path).stem
    if os.path.isdir(pdf_arg):
        return os.path.join(pdf_arg, f"{stem}_storyboard.pdf")
    return f"{stem}_storyboard.pdf"


def _process_single_video(
    args: argparse.Namespace,
    video_input: str,
    output_path: str,
    pdf_path: str | None,
    interval: float,
    show_progress: bool,
) -> None:
    """Process a single video through the full pipeline."""
    download_dir: str | None = None
    try:
        if is_url(video_input):
            download_dir = tempfile.mkdtemp(prefix="vmosaic_dl_")
            downloaded_path = os.path.join(download_dir, "video.mp4")

            if show_progress:
                progress = _make_progress(
                    BarColumn(bar_width=30),
                    TextColumn("[dim]{task.percentage:>5.1f}%[/dim]"),
                )
                with progress:
                    task = progress.add_task("Downloading", total=100)

                    def on_download(percent: float) -> None:
                        progress.update(task, completed=percent)

                    download_video(
                        video_input,
                        downloaded_path,
                        quality=args.quality,
                        on_progress=on_download,
                    )
                    progress.update(task, completed=100)
            else:
                download_video(video_input, downloaded_path, quality=args.quality)

            video_path = downloaded_path
        else:
            video_path = video_input
            if not os.path.isfile(video_path):
                raise VideoMosaicError(f"file not found → {video_path}")
            if args.quality:
                console.print(
                    "[warning]Warning:[/warning] --quality is only used with URL inputs, ignoring."
                )

        # Probe video
        info = get_video_info(video_path)
        duration = info["duration"]
        total_frames_est = round(info["fps"] * duration)
        console.print(
            f"\n[label]Video:[/label] {info['width']}×{info['height']}, "
            f"{duration:.1f}s, ~{total_frames_est} frames @ {info['fps']:.2f} fps\n"
        )

        # Resolve trim options
        try:
            trim_start = parse_timestamp(args.trim_start) if args.trim_start else None
            trim_end = parse_timestamp(args.trim_end) if args.trim_end else None
        except ValueError as e:
            raise VideoMosaicError(str(e))

        if trim_start is not None and trim_end is not None and trim_start >= trim_end:
            raise VideoMosaicError(
                f"--from ({fmt_timestamp(trim_start)}) must be before "
                f"--to ({fmt_timestamp(trim_end)})."
            )
        if trim_start is not None and trim_start > duration:
            raise VideoMosaicError(
                f"--from ({fmt_timestamp(trim_start)}) is beyond video duration "
                f"({fmt_timestamp(duration)})."
            )
        if trim_end is not None and trim_end > duration:
            console.print(
                f"[warning]Warning:[/warning] --to exceeds duration, "
                f"clamping to {fmt_timestamp(duration)}."
            )
            trim_end = duration

        # Resolve options
        thumb_width = args.thumb_width if args.thumb_width is not None else info["width"]

        if trim_start is not None or trim_end is not None:
            ts = trim_start or 0.0
            te = trim_end or duration
            console.print(f"[dim]  Trimming: {fmt_timestamp(ts)} → {fmt_timestamp(te)}[/dim]")

        # Extract frames
        tmp_dir = tempfile.mkdtemp(prefix="vmosaic_")
        try:
            # Compute trimmed duration for progress estimation
            trimmed_s = trim_start or 0.0
            trimmed_e = trim_end or duration
            trimmed_duration = trimmed_e - trimmed_s

            if args.all:
                estimated = max(1, round(info["fps"] * trimmed_duration))
                if show_progress:
                    progress = _make_progress(BarColumn(bar_width=30), MofNCompleteColumn())
                    with progress:
                        task = progress.add_task("Extracting all frames", total=estimated)

                        def on_extract(current: int, total: int) -> None:
                            progress.update(task, completed=current)

                        frames = extract_all_frames(
                            video_path,
                            tmp_dir,
                            duration,
                            trim_start,
                            trim_end,
                            on_progress=on_extract,
                            estimated_frames=estimated,
                        )
                        progress.update(
                            task,
                            completed=len(frames),
                            description=f"Extracted {len(frames)} frames",
                        )
                else:
                    frames = extract_all_frames(
                        video_path,
                        tmp_dir,
                        duration,
                        trim_start,
                        trim_end,
                    )
            elif args.every:
                estimated = max(1, round(trimmed_duration / interval))
                if show_progress:
                    progress = _make_progress(BarColumn(bar_width=30), MofNCompleteColumn())
                    with progress:
                        task = progress.add_task(
                            f"Extracting (1 every {interval}s)",
                            total=estimated,
                        )

                        def on_extract(current: int, total: int) -> None:
                            progress.update(task, completed=current)

                        frames = extract_every_n_seconds(
                            video_path,
                            tmp_dir,
                            interval,
                            trim_start,
                            trim_end,
                            on_progress=on_extract,
                            estimated_frames=estimated,
                        )
                        progress.update(
                            task,
                            completed=len(frames),
                            description=f"Extracted {len(frames)} frames",
                        )
                else:
                    frames = extract_every_n_seconds(
                        video_path,
                        tmp_dir,
                        interval,
                        trim_start,
                        trim_end,
                    )
            elif args.scenes:
                progress = _make_progress()
                with progress:
                    task = progress.add_task("Detecting scene changes …", total=1)
                    frames = extract_scene_changes(
                        video_path,
                        tmp_dir,
                        threshold=args.scene_threshold,
                        start=trim_start,
                        end=trim_end,
                    )
                    progress.update(
                        task,
                        completed=1,
                        description=f"Detected {len(frames)} scene changes",
                    )
            else:
                n = args.frames
                if show_progress:
                    progress = _make_progress(BarColumn(bar_width=30), MofNCompleteColumn())
                    with progress:
                        task = progress.add_task("Extracting frames", total=n)

                        def on_extract(current: int, total: int) -> None:
                            progress.update(task, completed=current)

                        frames = extract_n_frames(
                            video_path,
                            tmp_dir,
                            n,
                            duration,
                            trim_start,
                            trim_end,
                            on_progress=on_extract,
                        )
                        progress.update(
                            task,
                            description=f"Extracted {len(frames)} frames",
                        )
                else:
                    frames = extract_n_frames(
                        video_path,
                        tmp_dir,
                        n,
                        duration,
                        trim_start,
                        trim_end,
                    )

            if not frames:
                raise VideoMosaicError(
                    "no frames were extracted. Check your trim range and input file."
                )

            # Filter
            if args.skip_black or args.skip_dupes:
                if show_progress:
                    progress = _make_progress(BarColumn(bar_width=30), MofNCompleteColumn())
                    with progress:
                        task = progress.add_task("Filtering frames", total=len(frames))

                        def on_filter(current: int, total: int) -> None:
                            progress.update(task, completed=current)

                        frames, removed = filter_frames(
                            frames,
                            args.skip_black,
                            args.skip_dupes,
                            on_progress=on_filter,
                        )
                        desc = f"Filtered {len(frames)} frames"
                        if removed:
                            desc += f" [dim](-{removed})[/dim]"
                        progress.update(task, description=desc)
                else:
                    frames, removed = filter_frames(
                        frames,
                        args.skip_black,
                        args.skip_dupes,
                    )

            if not frames:
                raise VideoMosaicError(
                    "all frames were filtered out. Try relaxing --skip-black / --skip-dupes."
                )

            # Reverse
            if args.reverse:
                frames.reverse()
                console.print("[dim]  Reversed frame order[/dim]")

            # Auto-reduce thumb width if mosaic would be too large
            n_frames = len(frames)
            cols_est = args.cols or math.ceil(math.sqrt(n_frames))
            rows_est = math.ceil(n_frames / cols_est)
            est_pixels = (thumb_width * cols_est) * (thumb_width * rows_est)
            if est_pixels > MAX_CANVAS_PIXELS and args.thumb_width is None:
                scale = (MAX_CANVAS_PIXELS / est_pixels) ** 0.5
                thumb_width = max(120, int(thumb_width * scale))
                console.print(
                    f"[warning]Note:[/warning] auto-scaled thumbnails to {thumb_width}px wide "
                    f"({n_frames} frames would exceed "
                    f"{MAX_CANVAS_PIXELS // 1_000_000}MP limit)"
                )

            # Header info
            header_info = None if args.no_header else info

            # Compose mosaic
            if show_progress:
                progress = _make_progress(BarColumn(bar_width=30), MofNCompleteColumn())
                with progress:
                    task = progress.add_task("Composing mosaic", total=n_frames)

                    def on_compose(current: int, total: int) -> None:
                        progress.update(task, completed=current)

                    canvas = compose_mosaic(
                        frames,
                        output_path,
                        cols=args.cols,
                        thumb_width=thumb_width,
                        padding=args.padding,
                        bg_color=args.bg,
                        labels=args.labels,
                        header_info=header_info,
                        on_progress=on_compose,
                    )
                    canvas_w, canvas_h = canvas.size
                    canvas.close()
                    progress.update(
                        task,
                        completed=n_frames,
                        description=(
                            f"Saved [bold]{output_path}[/bold] [dim]({canvas_w}×{canvas_h})[/dim]"
                        ),
                    )
            else:
                canvas = compose_mosaic(
                    frames,
                    output_path,
                    cols=args.cols,
                    thumb_width=thumb_width,
                    padding=args.padding,
                    bg_color=args.bg,
                    labels=args.labels,
                    header_info=header_info,
                )
                canvas_w, canvas_h = canvas.size
                canvas.close()

            # PDF export
            if pdf_path:
                progress = _make_progress()
                with progress:
                    task = progress.add_task("Exporting PDF …", total=1)
                    export_pdf(
                        frames,
                        pdf_path,
                        thumb_width=min(thumb_width, 480),
                        cols=args.cols or 4,
                        header_info=header_info,
                    )
                    progress.update(
                        task,
                        completed=1,
                        description=f"Saved [bold]{pdf_path}[/bold]",
                    )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    finally:
        if download_dir:
            shutil.rmtree(download_dir, ignore_errors=True)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Validate numeric arguments
    if args.frames is not None and args.frames < 1:
        _error("--frames must be at least 1.")
    if args.cols is not None and args.cols < 1:
        _error("--cols must be at least 1.")
    if args.thumb_width is not None and args.thumb_width < 1:
        _error("--thumb-width must be at least 1.")
    if args.padding < 0:
        _error("--padding must not be negative.")
    if args.quality is not None and args.quality < 1:
        _error("--quality must be at least 1.")
    if args.scene_threshold < 0.0 or args.scene_threshold > 1.0:
        _error("--scene-threshold must be between 0.0 and 1.0.")

    # Validate interval early
    interval: float = 0.0
    if args.every:
        try:
            interval = parse_interval(args.every)
        except ValueError as e:
            _error(str(e))

    inputs: list[str] = args.input
    batch = len(inputs) > 1
    show_progress = not args.no_progress

    # Validate batch + output compatibility
    if batch and args.output != "mosaic.jpg" and not os.path.isdir(args.output):
        if Path(args.output).suffix:
            _error(
                f"Cannot use -o '{args.output}' (a specific file) with multiple inputs. "
                "Use -o <directory> or omit -o for auto-naming."
            )
    if batch and args.pdf and Path(args.pdf).suffix and not os.path.isdir(args.pdf):
        _error(
            f"Cannot use --pdf '{args.pdf}' (a specific file) with multiple inputs. "
            "Use --pdf <directory> or omit --pdf."
        )

    t_start_time = time.monotonic()
    failed: list[tuple[str, str]] = []

    for idx, video_input in enumerate(inputs):
        if batch:
            console.print(
                f"\n[label]Processing video {idx + 1}/{len(inputs)}:[/label] "
                f"{os.path.basename(video_input)}"
            )
            console.print("[dim]" + "\u2500" * 60 + "[/dim]")

        output_path = _resolve_output_path(video_input, args.output, batch)
        pdf_path = _resolve_pdf_path(video_input, args.pdf, batch)

        try:
            _process_single_video(
                args,
                video_input,
                output_path,
                pdf_path,
                interval,
                show_progress,
            )
            if args.open:
                _open_file(output_path)
        except VideoMosaicError as e:
            if batch:
                console.print(f"[error]Error:[/error] {e}")
                failed.append((video_input, str(e)))
            else:
                _error(str(e))

    elapsed = time.monotonic() - t_start_time
    if batch:
        succeeded = len(inputs) - len(failed)
        console.print(f"\n[dim]{'─' * 60}[/dim]")
        console.print(
            f"\n[label]Batch complete:[/label] {succeeded}/{len(inputs)} succeeded "
            f"in {elapsed:.1f}s"
        )
        if failed:
            console.print("[error]Failed:[/error]")
            for name, err in failed:
                console.print(f"  {os.path.basename(name)}: {err}")
            sys.exit(1)
    else:
        console.print(f"\n[dim]Done in {elapsed:.1f}s[/dim]")


if __name__ == "__main__":
    main()
