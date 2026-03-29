# video-mosaic

Extract frames from a video and arrange them into a single mosaic image.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
[![PyPI](https://img.shields.io/pypi/v/video-mosaic)](https://pypi.org/project/video-mosaic/)

## What it does

`video-mosaic` takes a video file (or URL), extracts frames, and composes them into a grid — like a contact sheet or storyboard. It includes a header with video metadata and optional timestamps on each frame. Supports YouTube, Twitter/X, TikTok, Instagram, and [any site supported by yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

```
┌─────────────────────────────────────────┐
│  filename.mp4                           │
│  1920×1080  •  30.2s  •  30.00 fps      │
├──────┬──────┬──────┬──────┬──────┬──────┤
│  #1  │  #2  │  #3  │  #4  │  #5  │  #6  │
│00:00 │00:05 │00:10 │00:15 │00:20 │00:25 │
├──────┼──────┼──────┼──────┼──────┼──────┤
│  #7  │  #8  │  #9  │ #10  │ #11  │ #12  │
│00:30 │00:35 │00:40 │00:45 │00:50 │00:55 │
└──────┴──────┴──────┴──────┴──────┴──────┘
```

## Installation

### With Homebrew (macOS)

```bash
brew tap GonzaloFuentes28/tap
brew install video-mosaic
```

### With pip

```bash
pip install video-mosaic
```

### From source

```bash
git clone https://github.com/GonzaloFuentes28/video-mosaic.git
cd video-mosaic
pip install .
```

### Prerequisites

**ffmpeg** must be installed and available in your `$PATH`.

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Arch
sudo pacman -S ffmpeg
```

To download videos from URLs (YouTube, Twitter/X, TikTok, etc.), you also need **yt-dlp**:

```bash
brew install yt-dlp   # macOS
pip install yt-dlp     # or via pip
```

## Quick start

```bash
# 48 evenly-spaced frames with timestamps
video-mosaic video.mp4 --frames 48 --labels

# One frame every 5 seconds
video-mosaic video.mp4 --every 5s -o contact-sheet.jpg

# Every single frame of a short clip
video-mosaic clip.mp4 --all -o all-frames.png

# From a URL (requires yt-dlp)
video-mosaic "https://youtube.com/watch?v=abc" --frames 48 --quality 720
video-mosaic "https://x.com/user/status/123" --frames 24
```

## Usage

```
video-mosaic INPUT [options]
```

### Frame selection (pick one)

| Flag | Description |
|---|---|
| `--frames N` | Extract exactly N frames, evenly distributed |
| `--every INTERVAL` | One frame per interval (`5s`, `500ms`, `0.5`) |
| `--all` | Every single frame (careful with long videos) |

### Trimming

| Flag | Description |
|---|---|
| `--from TIME` | Start time (`1:30`, `90`, `0:05.5`) |
| `--to TIME` | End time (`2:30`, `150`) |

```bash
# Frames only from the first minute
video-mosaic video.mp4 --frames 24 --from 0:00 --to 1:00
```

### Filtering

| Flag | Description |
|---|---|
| `--skip-black` | Exclude mostly-black frames |
| `--skip-dupes` | Exclude near-duplicate consecutive frames |

```bash
# Clean up a screencast with lots of static frames
video-mosaic screencast.mp4 --every 1s --skip-dupes --skip-black
```

### Layout

| Flag | Default | Description |
|---|---|---|
| `--cols N` | auto (√n) | Number of columns |
| `--thumb-width PX` | native | Thumbnail width in pixels |
| `--padding PX` | 2 | Gap between frames |
| `--bg COLOR` | #1a1a1a | Background color (hex) |
| `--labels` | off | Show frame number + timestamp |
| `--no-header` | — | Hide video info header |
| `--reverse` | — | Reverse frame order |

```bash
# Custom layout: 10 columns, smaller thumbnails, white background
video-mosaic video.mp4 --frames 100 --cols 10 --thumb-width 200 --bg "#ffffff"
```

### Output

| Flag | Default | Description |
|---|---|---|
| `-o PATH` | mosaic.jpg | Output image (.jpg, .png, .webp) |
| `--pdf PATH` | — | Also export as multi-page PDF storyboard |

```bash
# Image + PDF storyboard
video-mosaic video.mp4 --frames 48 --labels --pdf storyboard.pdf
```

### URL downloads

| Flag | Description |
|---|---|
| `--quality PX` | Max video height for URL downloads (e.g. `720`, `1080`) |

Requires [yt-dlp](https://github.com/yt-dlp/yt-dlp): `pip install yt-dlp` or `brew install yt-dlp`.

### Other

| Flag | Description |
|---|---|
| `--open` | Open the output image after saving |
| `--no-progress` | Disable progress bar |

## Examples

```bash
# Quick overview of a movie trailer
video-mosaic trailer.mp4 -o overview.jpg --frames 36 --cols 6 --labels

# Frame-by-frame analysis of a 2-second clip
video-mosaic clip.mp4 -o analysis.png --all --labels

# Every 10 seconds of a long lecture, skip static slides
video-mosaic lecture.mp4 -o sheet.webp --every 10s --skip-dupes --thumb-width 400

# Just the intro of a video, reversed, as PDF
video-mosaic video.mp4 --frames 20 --from 0:00 --to 0:30 --reverse --pdf intro.pdf
```

## Project structure

```
src/video_mosaic/
├── __init__.py   # Package root, version, VideoMosaicError
├── cli.py        # CLI argument parsing and orchestration
├── download.py   # URL video downloading via yt-dlp
├── probe.py      # Video metadata via ffprobe
├── extract.py    # Frame extraction strategies
├── filters.py    # Black frame / duplicate detection
├── mosaic.py     # Grid composition
├── pdf.py        # PDF storyboard export
└── utils.py      # Timestamp parsing, font loading
```

## Contributing

```bash
git clone https://github.com/GonzaloFuentes28/video-mosaic.git
cd video-mosaic
pip install -e ".[dev]"
```

## License

MIT — see [LICENSE](LICENSE).
