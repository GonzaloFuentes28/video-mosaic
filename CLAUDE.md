# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python CLI tool that extracts frames from a video file (or URL) using ffmpeg and composes them into a single mosaic/grid image (or PDF storyboard). Supports URL downloads via yt-dlp (CLI), trimming, filtering (black frames, duplicates), labeling, and layout customization. Published to PyPI as `video-mosaic`.

## Prerequisites

- **ffmpeg/ffprobe** must be installed and on PATH
- **Python 3.10+** (uses `X | Y` union type syntax)
- **yt-dlp** (optional, system CLI only — required for URL inputs, NOT a Python dependency)

## Commands

```bash
# Install (editable, with dev deps)
make dev              # pip install -e ".[dev]"

# Install (production)
make install          # pip install .

# Run
video-mosaic input.mp4 --frames 48 -o mosaic.jpg
video-mosaic "https://youtube.com/watch?v=abc" --frames 48 --quality 720

# Lint
make lint             # ruff check + ruff format --check on src/
make format           # auto-fix lint + format

# Test (34 E2E tests via pytest, requires ffmpeg)
make test

# Build & publish to PyPI
make build            # python -m build → dist/
make publish          # build + twine upload
```

## Build system

- Uses **hatchling** as build backend (`pyproject.toml`)
- Entry point: `video_mosaic.cli:main` → `video-mosaic` CLI command
- Dependencies: `Pillow>=9.0`, `rich>=13.0`
- Dev dependencies: `build`, `twine`, `ruff`, `pytest`
- yt-dlp is a **system CLI dependency only** (not a Python package dependency) — used via subprocess
- Ruff config: target Python 3.10, line length 100
- Version is tracked in both `pyproject.toml` and `src/video_mosaic/__init__.py` — keep them in sync

## Publishing

- **PyPI**: GitHub Actions workflow (`.github/workflows/publish.yml`) triggers on `v*` tags using trusted publishing. Just `git tag vX.Y.Z && git push origin vX.Y.Z`.
- **Homebrew**: Formula in separate repo `GonzaloFuentes28/homebrew-tap`. Uses `depends_on "pillow"` (bottled, no compilation). When releasing a new version, update the formula URL and SHA256 in that repo.
- After tagging, create a GitHub release with `gh release create vX.Y.Z`.

## Architecture

The pipeline flows linearly through these modules (all under `src/video_mosaic/`):

1. **`__init__.py`** — Package root. Defines `__version__` and `VideoMosaicError` base exception.
2. **`cli.py`** — Entry point. Parses args, validates inputs, orchestrates the pipeline. `main()` is an orchestrator that loops over inputs (batch mode), calling `_process_single_video()` for each. Uses `rich` for colored output, progress bars, and spinners. Catches `VideoMosaicError` from all modules. Auto-scales thumbnail width if mosaic would exceed pixel budget. Shows elapsed time. `--open` opens result in OS viewer.
3. **`download.py`** — URL detection (`is_url`) and video download via yt-dlp **subprocess** (not Python library). Parses yt-dlp's progress output via regex for progress callbacks. Downloads to a unique temp directory.
4. **`probe.py`** — Calls `ffprobe` to get video metadata (duration, fps, resolution, filename). Returns a dict used throughout. Validates video stream exists and has valid dimensions.
5. **`extract.py`** — Four extraction strategies, all writing JPEG frames to a temp dir:
   - `extract_all_frames` — every frame via ffmpeg bulk export (with progress via `-progress pipe:1`)
   - `extract_every_n_seconds` — uses ffmpeg `fps=1/N` filter (with progress via `-progress pipe:1`)
   - `extract_n_frames` — seeks to N evenly-spaced timestamps (concurrent via `ThreadPoolExecutor`, up to 8 workers)
   - `extract_scene_changes` — uses ffmpeg `select='gt(scene,T)',showinfo` filter to detect scene cuts
6. **`filters.py`** — Post-extraction filtering. `is_black_frame` checks average luminance; `is_duplicate` downscales to 64x64 grayscale and compares pixel similarity. Supports progress callback. Returns `(filtered_frames, removed_count)`.
7. **`mosaic.py`** — Composes the grid image. Auto-calculates columns (sqrt of frame count), draws optional header with video metadata, optional per-frame labels with timestamps. Has `MAX_CANVAS_PIXELS` safety limit (178MP, aligned with Pillow).
8. **`pdf.py`** — Multi-page PDF storyboard export using Pillow's PDF save. A4-ish layout with margins. Header only on first page. Closes all page images after save.
9. **`utils.py`** — Timestamp parsing/formatting (handles NaN/Inf), interval parsing with validation, and font loading (Linux/macOS/Windows paths, falls back to Pillow default).

### Error handling

All modules raise `VideoMosaicError` (defined in `__init__.py`) for non-recoverable errors. Only `cli.py` calls `sys.exit()`. All subprocess calls have timeouts.

### Key data type

Frames are passed between modules as `list[tuple[Path, float]]` — file path and timestamp in seconds.

### CLI output

Uses `rich` library (not tqdm) for all terminal output: progress bars with frame counters for all extraction modes and mosaic composition, colored status messages, and a custom `_CheckColumn` that shows spinner → ✓ on completion.

### CI

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push/PR to main:
- **lint**: `ruff check` + `ruff format --check` on `src/`
- **test**: `pytest tests/` on Python 3.10, 3.12, 3.13 (installs ffmpeg via apt)
