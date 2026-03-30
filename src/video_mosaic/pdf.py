"""PDF storyboard export."""

import math
from pathlib import Path

from PIL import Image, ImageDraw

from .utils import fmt_timestamp, load_font


def export_pdf(
    frames: list[tuple[Path, float]],
    pdf_path: str,
    thumb_width: int = 720,
    cols: int = 4,
    header_info: dict | None = None,
) -> None:
    """Export frames as a multi-page PDF storyboard."""
    if not frames:
        raise ValueError("No frames to export as PDF.")

    with Image.open(frames[0][0]) as sample:
        if sample.width == 0:
            raise ValueError("First frame has zero width — corrupted image.")
        aspect = sample.height / sample.width
    thumb_height = int(thumb_width * aspect)

    # A4-ish layout: fit cols across the page with margins
    margin = 40
    padding = 8
    cell_w = thumb_width + padding
    cell_h = thumb_height + padding + 30  # space for timestamp

    page_w = cols * cell_w + 2 * margin
    header_h = 80 if header_info else 0
    content_height = int(page_w * 1.414) - 2 * margin
    rows_per_page = max(1, content_height // cell_h)
    page_h = rows_per_page * cell_h + 2 * margin + header_h

    font = load_font(max(11, int(thumb_width * 0.03)))
    header_font = load_font(max(14, int(thumb_width * 0.04)))

    pages: list[Image.Image] = []
    frames_per_page = cols * rows_per_page

    for page_idx in range(math.ceil(len(frames) / frames_per_page)):
        page = Image.new("RGB", (page_w, page_h), "#ffffff")
        draw = ImageDraw.Draw(page)

        y_offset = margin

        # Header on first page only
        if page_idx == 0 and header_info:
            draw.text((margin, y_offset), header_info["filename"], fill="#222222", font=header_font)
            meta = (
                f"{header_info['width']}×{header_info['height']}  •  "
                f"{header_info['duration']:.1f}s  •  "
                f"{header_info['fps']:.2f} fps"
            )
            draw.text((margin, y_offset + 30), meta, fill="#666666", font=font)
            y_offset += header_h

        chunk = frames[page_idx * frames_per_page : (page_idx + 1) * frames_per_page]
        for i, (fpath, ts) in enumerate(chunk):
            col = i % cols
            row = i // cols
            x = margin + col * cell_w
            y = y_offset + row * cell_h

            with Image.open(fpath) as img:
                resized = img.resize((thumb_width, thumb_height), Image.LANCZOS)
            page.paste(resized, (x, y))
            resized.close()

            global_idx = page_idx * frames_per_page + i
            draw.text(
                (x + 2, y + thumb_height + 4),
                f"#{global_idx + 1}  {fmt_timestamp(ts)}",
                fill="#444444",
                font=font,
            )

        # Page number
        page_label = f"Page {page_idx + 1}"
        draw.text(
            (page_w - margin - 80, page_h - margin - 10), page_label, fill="#aaaaaa", font=font
        )
        pages.append(page)

    if pages:
        pages[0].save(pdf_path, save_all=True, append_images=pages[1:], resolution=150)
        for p in pages:
            p.close()
