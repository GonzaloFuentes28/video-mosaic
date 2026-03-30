"""End-to-end tests for video-mosaic CLI.

Each test invokes the CLI via subprocess (just like a user would) and verifies
that the expected output files are produced and are valid images.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run the video-mosaic CLI and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "video_mosaic.cli", *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=120,
    )


def assert_valid_image(path: Path, min_width: int = 10, min_height: int = 10) -> Image.Image:
    """Assert that the path is a valid image and meets minimum dimensions."""
    assert path.exists(), f"Output file not found: {path}"
    img = Image.open(path)
    assert img.width >= min_width, f"Image too narrow: {img.width}px"
    assert img.height >= min_height, f"Image too short: {img.height}px"
    return img


# ─── --frames mode ────────────────────────────────────────────────


class TestFramesMode:
    def test_basic(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "6", "-o", str(out))
        img = assert_valid_image(out)
        img.close()

    def test_with_labels(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "6", "--labels", "-o", str(out))
        img = assert_valid_image(out)
        img.close()

    def test_with_cols(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "6", "--cols", "3", "-o", str(out))
        img = assert_valid_image(out)
        img.close()

    def test_single_frame(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "1", "-o", str(out))
        img = assert_valid_image(out)
        img.close()

    def test_png_output(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.png"
        run_cli(str(test_video), "--frames", "4", "-o", str(out))
        img = assert_valid_image(out)
        assert img.format == "PNG"
        img.close()

    def test_webp_output(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.webp"
        run_cli(str(test_video), "--frames", "4", "-o", str(out))
        img = assert_valid_image(out)
        img.close()

    def test_no_header(self, test_video: Path, output_dir: Path):
        out_with = output_dir / "with_header.jpg"
        out_without = output_dir / "without_header.jpg"
        run_cli(str(test_video), "--frames", "4", "-o", str(out_with))
        run_cli(str(test_video), "--frames", "4", "--no-header", "-o", str(out_without))
        img_with = Image.open(out_with)
        img_without = Image.open(out_without)
        # Without header should be shorter
        assert img_without.height < img_with.height
        img_with.close()
        img_without.close()

    def test_reverse(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "4", "--reverse", "-o", str(out))
        assert_valid_image(out).close()

    def test_thumb_width(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "4", "--thumb-width", "100", "-o", str(out))
        assert_valid_image(out).close()

    def test_no_progress(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "4", "--no-progress", "-o", str(out))
        assert_valid_image(out).close()


# ─── --every mode ─────────────────────────────────────────────────


class TestEveryMode:
    def test_seconds(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--every", "1s", "-o", str(out))
        img = assert_valid_image(out)
        img.close()

    def test_milliseconds(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--every", "2000ms", "-o", str(out))
        assert_valid_image(out).close()

    def test_plain_number(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--every", "2", "-o", str(out))
        assert_valid_image(out).close()


# ─── --all mode ───────────────────────────────────────────────────


class TestAllMode:
    def test_basic(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--all", "-o", str(out))
        assert_valid_image(out).close()


# ─── --scenes mode ────────────────────────────────────────────────


class TestScenesMode:
    def test_basic(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--scenes", "-o", str(out))
        assert_valid_image(out).close()

    def test_low_threshold(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--scenes", "--scene-threshold", "0.1", "-o", str(out))
        assert_valid_image(out).close()

    def test_high_threshold(self, test_video: Path, output_dir: Path):
        """High threshold may detect fewer or no scenes — should not crash."""
        result = run_cli(
            str(test_video),
            "--scenes",
            "--scene-threshold",
            "0.99",
            "-o",
            str(output_dir / "mosaic.jpg"),
            check=False,
        )
        # Either succeeds (found some scenes) or exits with error (no frames)
        assert result.returncode in (0, 1)


# ─── Trimming ─────────────────────────────────────────────────────


class TestTrimming:
    def test_from(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "4", "--from", "2", "-o", str(out))
        assert_valid_image(out).close()

    def test_to(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "4", "--to", "4", "-o", str(out))
        assert_valid_image(out).close()

    def test_from_and_to(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "4", "--from", "1", "--to", "5", "-o", str(out))
        assert_valid_image(out).close()


# ─── Filtering ────────────────────────────────────────────────────


class TestFiltering:
    def test_skip_dupes(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "12", "--skip-dupes", "-o", str(out))
        assert_valid_image(out).close()

    def test_skip_black(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(str(test_video), "--frames", "12", "--skip-black", "-o", str(out))
        assert_valid_image(out).close()

    def test_both_filters(self, test_video: Path, output_dir: Path):
        out = output_dir / "mosaic.jpg"
        run_cli(
            str(test_video),
            "--frames",
            "12",
            "--skip-black",
            "--skip-dupes",
            "-o",
            str(out),
        )
        assert_valid_image(out).close()


# ─── PDF export ───────────────────────────────────────────────────


class TestPdfExport:
    def test_basic(self, test_video: Path, output_dir: Path):
        mosaic = output_dir / "mosaic.jpg"
        pdf = output_dir / "storyboard.pdf"
        run_cli(str(test_video), "--frames", "6", "-o", str(mosaic), "--pdf", str(pdf))
        assert_valid_image(mosaic).close()
        assert pdf.exists()
        assert pdf.stat().st_size > 0


# ─── Batch mode ───────────────────────────────────────────────────


class TestBatchMode:
    def test_two_inputs(self, test_video: Path, output_dir: Path):
        """Process the same video twice — produces two auto-named outputs."""
        # Copy the test video to create a "second" input with a different name
        import shutil

        video2 = output_dir / "second.mp4"
        shutil.copy2(test_video, video2)

        run_cli(str(test_video), str(video2), "--frames", "4", "-o", str(output_dir))

        out1 = output_dir / "test_mosaic.jpg"
        out2 = output_dir / "second_mosaic.jpg"
        assert_valid_image(out1).close()
        assert_valid_image(out2).close()

    def test_batch_with_pdf(self, test_video: Path, output_dir: Path):
        import shutil

        video2 = output_dir / "clip.mp4"
        shutil.copy2(test_video, video2)

        run_cli(
            str(test_video),
            str(video2),
            "--frames",
            "4",
            "-o",
            str(output_dir),
            "--pdf",
            str(output_dir),
        )

        assert (output_dir / "test_mosaic.jpg").exists()
        assert (output_dir / "clip_mosaic.jpg").exists()
        assert (output_dir / "test_storyboard.pdf").exists()
        assert (output_dir / "clip_storyboard.pdf").exists()

    def test_batch_specific_file_errors(self, test_video: Path, output_dir: Path):
        """Passing -o as a specific file with multiple inputs should fail."""
        import shutil

        video2 = output_dir / "second.mp4"
        shutil.copy2(test_video, video2)

        result = run_cli(
            str(test_video),
            str(video2),
            "--frames",
            "4",
            "-o",
            str(output_dir / "specific.jpg"),
            check=False,
        )
        assert result.returncode != 0


# ─── Error cases ──────────────────────────────────────────────────


class TestErrors:
    def test_missing_file(self, output_dir: Path):
        result = run_cli("nonexistent.mp4", "--frames", "4", check=False)
        assert result.returncode != 0

    def test_invalid_frames(self, test_video: Path):
        result = run_cli(str(test_video), "--frames", "0", check=False)
        assert result.returncode != 0

    def test_invalid_scene_threshold(self, test_video: Path):
        result = run_cli(
            str(test_video),
            "--scenes",
            "--scene-threshold",
            "2.0",
            check=False,
        )
        assert result.returncode != 0

    def test_mutually_exclusive_modes(self, test_video: Path):
        result = run_cli(str(test_video), "--frames", "4", "--all", check=False)
        assert result.returncode != 0

    def test_no_mode_specified(self, test_video: Path):
        result = run_cli(str(test_video), check=False)
        assert result.returncode != 0

    def test_trim_start_after_end(self, test_video: Path, output_dir: Path):
        result = run_cli(
            str(test_video),
            "--frames",
            "4",
            "--from",
            "5",
            "--to",
            "2",
            "-o",
            str(output_dir / "mosaic.jpg"),
            check=False,
        )
        assert result.returncode != 0


# ─── Help ─────────────────────────────────────────────────────────


class TestHelp:
    def test_help_flag(self):
        result = run_cli("--help", check=False)
        assert result.returncode == 0
        assert "video-mosaic" in result.stdout
        assert "--scenes" in result.stdout
        assert "--scene-threshold" in result.stdout
