"""video-mosaic — Extract frames from a video and compose them into a mosaic image."""

__version__ = "0.1.0"


class VideoMosaicError(RuntimeError):
    """Raised when a non-recoverable error occurs in the video-mosaic pipeline."""
