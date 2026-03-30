"""Shared fixtures for video-mosaic tests."""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a short synthetic test video with scene changes.

    Creates a 6-second video (24fps, 320x240) with 3 distinct 2-second scenes
    (red, green, blue) so that --scenes can detect transitions.
    """
    out = tmp_path_factory.mktemp("fixtures") / "test.mp4"

    # 3 color segments of 2s each → sharp scene changes at 2s and 4s
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "quiet",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:size=320x240:duration=2:rate=24",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:size=320x240:duration=2:rate=24",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=320x240:duration=2:rate=24",
            "-filter_complex",
            "[0][1][2]concat=n=3:v=1:a=0[out]",
            "-map",
            "[out]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ],
        check=True,
        timeout=30,
    )
    assert out.exists(), "ffmpeg failed to create test video"
    return out


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Provide a clean temp directory for test outputs."""
    return tmp_path
