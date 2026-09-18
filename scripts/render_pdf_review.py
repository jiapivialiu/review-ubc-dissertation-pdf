#!/usr/bin/env python3
"""Build compact contact sheets and selected detail renders without editing a thesis or dissertation PDF."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageDraw, ImageOps
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("Pillow is required. Use the PDF-capable workspace Python runtime.") from exc

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("pypdf is required. Use the PDF-capable workspace Python runtime.") from exc


def parse_pages(spec: str | None, maximum: int) -> set[int]:
    pages: set[int] = set()
    if not spec:
        return pages
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            pages.update(range(min(start, end), max(start, end) + 1))
        else:
            pages.add(int(part))
    invalid = sorted(page for page in pages if page < 1 or page > maximum)
    if invalid:
        raise ValueError(f"Page numbers outside 1-{maximum}: {invalid}")
    return pages


def finding_pages(path: Path | None) -> set[int]:
    if not path:
        return set()
    report = json.loads(path.read_text(encoding="utf-8"))
    pages: set[int] = set()
    for finding in report.get("findings", []):
        for page in finding.get("pdf_pages", []):
            if isinstance(page, int):
                pages.add(page)
    return pages


def run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise SystemExit("pdftoppm is required; install Poppler or use the bundled PDF runtime.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or "pdftoppm failed") from exc


def chunks(items: list[Path], size: int) -> Iterable[list[Path]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def build_contact_sheets(
    images: list[Path], labels: list[str], out_dir: Path, cols: int, rows: int
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_width, image_height, label_height, pad = 520, 680, 32, 10
    cell_height = image_height + label_height + pad * 2
    outputs: list[Path] = []
    page_offset = 0
    for sheet_number, group in enumerate(chunks(images, cols * rows), 1):
        used_cols = min(cols, len(group))
        used_rows = math.ceil(len(group) / cols)
        canvas = Image.new("RGB", (cell_width * used_cols, cell_height * used_rows), "#d9d9d9")
        draw = ImageDraw.Draw(canvas)
        for slot, image_path in enumerate(group):
            pdf_page = page_offset + slot + 1
            row, col = divmod(slot, cols)
            x, y = col * cell_width, row * cell_height
            with Image.open(image_path) as source:
                thumb = ImageOps.contain(source.convert("RGB"), (cell_width - 2 * pad, image_height))
            image_x = x + (cell_width - thumb.width) // 2
            image_y = y + label_height + pad + (image_height - thumb.height) // 2
            canvas.paste(thumb, (image_x, image_y))
            printed = labels[pdf_page - 1] if pdf_page <= len(labels) else "?"
            draw.text((x + pad, y + 8), f"PDF {pdf_page} | label {printed}", fill="black")
        output = out_dir / f"contact-{sheet_number:03d}.jpg"
        canvas.save(output, "JPEG", quality=78, optimize=True)
        outputs.append(output)
        page_offset += len(group)
    return outputs


def add_margin_overlay(
    source: Path, output: Path, page_width_pt: float, page_height_pt: float
) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    draw = ImageDraw.Draw(image)
    x_left = round(72 / page_width_pt * image.width)
    x_right = round((page_width_pt - 54) / page_width_pt * image.width)
    y_top = round(54 / page_height_pt * image.height)
    y_bottom = round((page_height_pt - 54) / page_height_pt * image.height)
    draw.rectangle((x_left, y_top, x_right, y_bottom), outline="#e00000", width=3)
    draw.text(
        (x_left + 8, y_top + 8),
        "UBC minimum body margins: L 1in; T/R/B 0.75in",
        fill="#e00000",
    )
    image.save(output, "PNG", optimize=True)


def render_details(
    pdf: Path, reader: PdfReader, pages: set[int], out_dir: Path,
    dpi: int, margin_overlay: bool,
) -> tuple[list[Path], list[Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    overlays: list[Path] = []
    for page in sorted(pages):
        prefix = out_dir / f"pdf-page-{page:04d}"
        run([
            "pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi),
            "-singlefile", "-png", str(pdf), str(prefix),
        ])
        rendered = prefix.with_suffix(".png")
        outputs.append(rendered)
        if margin_overlay:
            pdf_page = reader.pages[page - 1]
            overlay = out_dir / f"pdf-page-{page:04d}-margins.png"
            add_margin_overlay(
                rendered, overlay,
                float(pdf_page.mediabox.width), float(pdf_page.mediabox.height),
            )
            overlays.append(overlay)
    return outputs, overlays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pages", help="One-based detail pages, for example 1-12,40,72-74.")
    parser.add_argument("--findings", type=Path, help="Add pages referenced by a preflight JSON report.")
    parser.add_argument("--contact-dpi", type=int, default=72)
    parser.add_argument("--detail-dpi", type=int, default=180)
    parser.add_argument("--sheet-cols", type=int, default=3)
    parser.add_argument("--sheet-rows", type=int, default=4)
    parser.add_argument("--no-contact", action="store_true")
    parser.add_argument(
        "--margin-overlay", action="store_true",
        help="Also save selected detail pages with UBC minimum body margins overlaid.",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")
    if args.findings and not args.findings.is_file():
        parser.error(f"Findings JSON not found: {args.findings}")
    if min(args.contact_dpi, args.detail_dpi, args.sheet_cols, args.sheet_rows) < 1:
        parser.error("DPI and sheet dimensions must be positive.")

    reader = PdfReader(str(args.pdf))
    page_count = len(reader.pages)
    try:
        labels = list(reader.page_labels)
    except Exception:
        labels = [str(index) for index in range(1, page_count + 1)]

    selected = parse_pages(args.pages, page_count) | finding_pages(args.findings)
    args.out.mkdir(parents=True, exist_ok=True)
    contact_outputs: list[Path] = []

    if not args.no_contact:
        with tempfile.TemporaryDirectory(prefix="ubc-pdf-contact-") as temp_name:
            prefix = Path(temp_name) / "page"
            run([
                "pdftoppm", "-jpeg", "-jpegopt", "quality=65", "-r", str(args.contact_dpi),
                str(args.pdf), str(prefix),
            ])
            images = sorted(Path(temp_name).glob("page-*.jpg"))
            if len(images) != page_count:
                raise SystemExit(f"Expected {page_count} thumbnails, found {len(images)}")
            contact_outputs = build_contact_sheets(
                images, labels, args.out / "contact", args.sheet_cols, args.sheet_rows
            )

    detail_outputs, overlay_outputs = (
        render_details(
            args.pdf, reader, selected, args.out / "detail",
            args.detail_dpi, args.margin_overlay,
        ) if selected else ([], [])
    )
    print(
        f"contact_sheets={len(contact_outputs)} detail_pages={len(detail_outputs)} "
        f"margin_overlays={len(overlay_outputs)} out={args.out.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
