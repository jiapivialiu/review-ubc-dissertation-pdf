#!/usr/bin/env python3
"""Emit a compact, read-only preflight report for a UBC thesis or dissertation PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError:  # Report an unavailable geometry pass instead of hiding it.
    pdfplumber = None

try:
    from PIL import ImageDraw
except ImportError:  # Report an unavailable geometry pass instead of hiding it.
    ImageDraw = None

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("pypdf is required. Use the PDF-capable workspace Python runtime.") from exc


LETTER = (612.0, 792.0)
LETTER_TOLERANCE = 2.0
UBC_BODY_MARGINS_PT = {"left": 72.0, "right": 54.0, "top": 54.0, "bottom": 54.0}
UBC_PAGE_NUMBER_EDGE_PT = 36.0
GEOMETRY_TOLERANCE_PT = 1.5
GEOMETRY_RENDER_DPI = 96
INK_THRESHOLD = 250
BASE14 = {
    "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
    "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
    "Symbol", "ZapfDingbats",
}
SECTION_NAMES = {
    "abstract": {"abstract"},
    "lay_summary": {"lay summary", "lay summary of the dissertation"},
    "preface": {"preface"},
    "table_of_contents": {"table of contents", "contents"},
    "list_of_tables": {"list of tables"},
    "list_of_figures": {"list of figures"},
    "list_of_illustrations": {"list of illustrations"},
    "acknowledgements": {"acknowledgements", "acknowledgments"},
    "bibliography": {"bibliography", "references", "works cited"},
    "appendices": {"appendix", "appendices"},
}
FINAL_NAME = re.compile(
    r"^ubc_\d{4}_(?:february|may|september|november)_[a-z0-9-]+_[a-z0-9-]+\.pdf$"
)


def deref(value: Any) -> Any:
    try:
        return value.get_object()
    except Exception:
        return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_version(path: Path) -> str | None:
    with path.open("rb") as stream:
        match = re.search(rb"%PDF-(\d\.\d)", stream.read(1024))
    return match.group(1).decode("ascii") if match else None


def is_linearized(path: Path) -> bool:
    with path.open("rb") as stream:
        return b"/Linearized" in stream.read(4096)


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def normalized_line(line: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", line)).strip().casefold()


def page_xobjects(page: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    resources = deref(page.get("/Resources", {})) or {}
    xobjects = deref(resources.get("/XObject", {})) or {}
    for item in xobjects.values():
        obj = deref(item) or {}
        counts[str(obj.get("/Subtype", "/Unknown"))] += 1
    return counts


def content_length(page: Any) -> int:
    try:
        contents = page.get_contents()
        return len(contents.get_data()) if contents else 0
    except Exception:
        return 0


def font_descriptors(font: Any) -> list[Any]:
    font = deref(font) or {}
    descriptors: list[Any] = []
    if font.get("/FontDescriptor"):
        descriptors.append(deref(font["/FontDescriptor"]))
    descendants = deref(font.get("/DescendantFonts", [])) or []
    for descendant in descendants:
        child = deref(descendant) or {}
        if child.get("/FontDescriptor"):
            descriptors.append(deref(child["/FontDescriptor"]))
    return descriptors


def page_fonts(page: Any) -> list[dict[str, Any]]:
    resources = deref(page.get("/Resources", {})) or {}
    fonts = deref(resources.get("/Font", {})) or {}
    result = []
    for font in fonts.values():
        obj = deref(font) or {}
        base = str(obj.get("/BaseFont", "/Unknown")).lstrip("/")
        plain = re.sub(r"^[A-Z]{6}\+", "", base)
        descriptors = font_descriptors(obj)
        embedded = any(
            any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
            for descriptor in descriptors
            if descriptor
        )
        result.append(
            {
                "name": plain,
                "subtype": str(obj.get("/Subtype", "/Unknown")).lstrip("/"),
                "embedded": embedded,
                "base14": plain in BASE14,
            }
        )
    return result


def link_counts(page: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    for annotation in deref(page.get("/Annots", [])) or []:
        annot = deref(annotation) or {}
        if annot.get("/Subtype") != "/Link":
            continue
        action = deref(annot.get("/A", {})) or {}
        if action.get("/URI"):
            counts["external"] += 1
        elif annot.get("/Dest") or action.get("/D"):
            counts["internal"] += 1
        else:
            counts["unresolved"] += 1
    return counts


def outline_count(items: Any) -> int:
    total = 0
    for item in items or []:
        if isinstance(item, list):
            total += outline_count(item)
        else:
            total += 1
    return total


def label_kind(label: str) -> str:
    if re.fullmatch(r"[ivxlcdm]+", label):
        return "roman-lower"
    if re.fullmatch(r"[IVXLCDM]+", label):
        return "roman-upper"
    if re.fullmatch(r"\d+", label):
        return "arabic"
    return "other"


def label_segments(labels: list[str]) -> list[dict[str, Any]]:
    if not labels:
        return []
    segments = []
    start = 0
    kind = label_kind(labels[0])
    for index, label in enumerate(labels[1:], 1):
        new_kind = label_kind(label)
        if new_kind != kind:
            segments.append(
                {"pdf_pages": [start + 1, index], "kind": kind,
                 "labels": [labels[start], labels[index - 1]]}
            )
            start, kind = index, new_kind
    segments.append(
        {"pdf_pages": [start + 1, len(labels)], "kind": kind,
         "labels": [labels[start], labels[-1]]}
    )
    return segments


def object_bbox(obj: dict[str, Any]) -> tuple[float, float, float, float] | None:
    try:
        half_stroke = float(obj.get("linewidth") or 0) / 2
        return (
            float(obj["x0"]) - half_stroke,
            float(obj["top"]) - half_stroke,
            float(obj["x1"]) + half_stroke,
            float(obj["bottom"]) + half_stroke,
        )
    except (KeyError, TypeError, ValueError):
        return None


def page_number_boxes(
    page: Any, printed_label: str | None, tolerance: float
) -> tuple[list[tuple[float, float, float, float]], bool]:
    if not printed_label:
        return [], False
    label = normalized_line(printed_label)
    width, height = float(page.width), float(page.height)
    boxes = []
    too_close = False
    for word in page.extract_words(x_tolerance=2, y_tolerance=2):
        if normalized_line(str(word.get("text", ""))) != label:
            continue
        bbox = object_bbox(word)
        if not bbox:
            continue
        x0, top, x1, bottom = bbox
        x_mid, y_mid = (x0 + x1) / 2, (top + bottom) / 2
        near_vertical_edge = y_mid <= 144 or y_mid >= height - 144
        centered = abs(x_mid - width / 2) <= width * 0.12
        right_aligned = x_mid >= width * 0.72
        if not near_vertical_edge or not (centered or right_aligned):
            continue
        vertical_distance = y_mid if y_mid < height / 2 else height - y_mid
        if vertical_distance < UBC_PAGE_NUMBER_EDGE_PT - tolerance:
            too_close = True
        if right_aligned and width - x_mid < UBC_PAGE_NUMBER_EDGE_PT - tolerance:
            too_close = True
        boxes.append(bbox)
    return boxes, too_close


def rendered_ink_geometry(
    page: Any,
    number_boxes: list[tuple[float, float, float, float]],
    tolerance: float,
    resolution: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, float | None]]:
    """Measure visible rasterized ink, avoiding unclipped vector-path coordinates."""
    rendered = page.to_image(
        resolution=resolution, antialias=True, force_mediabox=False
    ).original.convert("L")
    scale_x = rendered.width / float(page.width)
    scale_y = rendered.height / float(page.height)

    # A printed page number is allowed outside the body box. Mask only its detected
    # word box, with small antialiasing/glyph padding; everything else remains tested.
    draw = ImageDraw.Draw(rendered)
    for x0, top, x1, bottom in number_boxes:
        pad_x, pad_y = 2 * scale_x, 2 * scale_y
        draw.rectangle(
            (
                max(0, round(x0 * scale_x - pad_x)),
                max(0, round(top * scale_y - pad_y)),
                min(rendered.width, round(x1 * scale_x + pad_x)),
                min(rendered.height, round(bottom * scale_y + pad_y)),
            ),
            fill=255,
        )

    ink = rendered.point(lambda value: 255 if value < INK_THRESHOLD else 0)
    overall = ink.getbbox()
    if overall:
        x0, top, x1, bottom = overall
        minima: dict[str, float | None] = {
            "left": x0 / scale_x,
            "right": (rendered.width - x1) / scale_x,
            "top": top / scale_y,
            "bottom": (rendered.height - bottom) / scale_y,
        }
    else:
        minima = {edge: None for edge in UBC_BODY_MARGINS_PT}

    width, height = float(page.width), float(page.height)
    regions = {
        "left": (0, 0, max(0, int((UBC_BODY_MARGINS_PT["left"] - tolerance) * scale_x)), rendered.height),
        "right": (min(rendered.width, int((width - UBC_BODY_MARGINS_PT["right"] + tolerance) * scale_x)), 0, rendered.width, rendered.height),
        "top": (0, 0, rendered.width, max(0, int((UBC_BODY_MARGINS_PT["top"] - tolerance) * scale_y))),
        "bottom": (0, min(rendered.height, int((height - UBC_BODY_MARGINS_PT["bottom"] + tolerance) * scale_y)), rendered.width, rendered.height),
    }
    edges: dict[str, dict[str, Any]] = {}
    for edge, region in regions.items():
        band = ink.crop(region)
        bbox = band.getbbox()
        if not bbox:
            continue
        histogram = band.histogram()
        visible_pixels = sum(histogram[1:])
        clearance = minima[edge]
        overflow = (
            UBC_BODY_MARGINS_PT[edge] - clearance
            if clearance is not None else 0
        )
        edges[edge] = {
            "max_overflow_pt": round(max(0.0, overflow), 2),
            "visible_ink_pixels": visible_pixels,
            "detection": "rendered-ink",
        }
    return edges, minima


def scan_geometry(
    path: Path, labels: list[str], tolerance: float, resolution: int
) -> dict[str, Any]:
    if pdfplumber is None or ImageDraw is None:
        missing = []
        if pdfplumber is None:
            missing.append("pdfplumber")
        if ImageDraw is None:
            missing.append("Pillow")
        return {"available": False, "reason": f"Missing dependency: {', '.join(missing)}"}

    violations = []
    missing_numbers: list[int] = []
    close_numbers: list[int] = []
    minima = {edge: float("inf") for edge in UBC_BODY_MARGINS_PT}
    pages_checked = 0

    with pdfplumber.open(str(path)) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            pages_checked += 1
            label = labels[page_number - 1] if page_number <= len(labels) else None
            number_boxes, number_too_close = page_number_boxes(page, label, tolerance)
            if page_number > 1 and label and not number_boxes:
                missing_numbers.append(page_number)
            if number_too_close:
                close_numbers.append(page_number)

            edges, page_minima = rendered_ink_geometry(
                page, number_boxes, tolerance, resolution
            )
            for edge, clearance in page_minima.items():
                if clearance is not None:
                    minima[edge] = min(minima[edge], clearance)
            if edges:
                violations.append(
                    {"pdf_page": page_number, "printed_label": label, "edges": edges}
                )
            page.close()

    finite_minima = {
        edge: round(value, 2) if value != float("inf") else None
        for edge, value in minima.items()
    }
    return {
        "available": True,
        "coordinate_system": "PDF points from visible page edges; 72 points = 1 inch",
        "method": f"{resolution}-DPI rendered-ink scan after masking only detected page-number boxes",
        "render_dpi": resolution,
        "ink_threshold_gray": INK_THRESHOLD,
        "required_body_margins_pt": UBC_BODY_MARGINS_PT,
        "page_number_min_edge_distance_pt": UBC_PAGE_NUMBER_EDGE_PT,
        "tolerance_pt": tolerance,
        "pages_checked": pages_checked,
        "document_min_clearance_pt": finite_minima,
        "violations": violations,
        "missing_visible_page_number_pages": compact_pages(missing_numbers),
        "page_number_too_close_pages": compact_pages(close_numbers),
    }


def detect_sections(page_texts: list[str]) -> tuple[dict[str, int], list[int]]:
    sections: dict[str, int] = {}
    chapters: list[int] = []
    for page_number, text in enumerate(page_texts, 1):
        lines = [normalized_line(line) for line in text.splitlines()[:25]]
        top_lines = [line for line in lines if line][:4]
        for key, candidates in SECTION_NAMES.items():
            if key not in sections and any(line in candidates for line in lines):
                sections[key] = page_number
        if any(
            re.fullmatch(r"chapter\s+\d+(?:\s*[:\-]?\s*[^.].*)?", line)
            for line in top_lines
        ):
            chapters.append(page_number)
    return sections, chapters


def section_word_count(
    page_texts: list[str], start_page: int, end_page: int, start_names: set[str], end_names: set[str]
) -> int:
    lines: list[str] = []
    for page_index in range(start_page - 1, end_page):
        lines.extend(page_texts[page_index].splitlines())
    started = False
    body: list[str] = []
    for line in lines:
        key = normalized_line(line)
        if not started:
            if key in start_names:
                started = True
            continue
        if key in end_names:
            break
        body.append(line)
    return len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", "\n".join(body)))


def compact_pages(pages: list[int], limit: int = 30) -> list[int | str]:
    if len(pages) <= limit:
        return pages
    return [*pages[:limit], f"+{len(pages) - limit} more"]


def compare_pdf(current_texts: list[str], current_reader: PdfReader, old_path: Path) -> dict[str, Any]:
    old_reader = PdfReader(str(old_path))
    if old_reader.is_encrypted:
        return {"error": "baseline PDF is encrypted"}
    old_texts = [page.extract_text() or "" for page in old_reader.pages]
    overlap = min(len(current_texts), len(old_texts))
    changed_text = [
        index + 1
        for index in range(overlap)
        if normalized_text(current_texts[index]) != normalized_text(old_texts[index])
    ]
    changed_layout = []
    for index in range(overlap):
        current = current_reader.pages[index]
        old = old_reader.pages[index]
        current_box = (round(float(current.mediabox.width), 2), round(float(current.mediabox.height), 2), int(current.rotation or 0))
        old_box = (round(float(old.mediabox.width), 2), round(float(old.mediabox.height), 2), int(old.rotation or 0))
        if current_box != old_box:
            changed_layout.append(index + 1)
    return {
        "baseline": str(old_path.resolve()),
        "baseline_sha256": sha256_file(old_path),
        "page_counts": [len(old_texts), len(current_texts)],
        "changed_text_pages": compact_pages(changed_text),
        "changed_layout_pages": compact_pages(changed_layout),
        "note": "Page-index comparison; insertions can shift downstream pages.",
    }


def inspect(
    path: Path, final_name: bool, compare: Path | None,
    skip_geometry: bool, geometry_tolerance: float, geometry_dpi: int,
) -> dict[str, Any]:
    version = pdf_version(path)
    reader = PdfReader(str(path))
    findings: list[dict[str, Any]] = []

    def add(severity: str, code: str, message: str, pages: list[int] | None = None) -> None:
        item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
        if pages:
            item["pdf_pages"] = compact_pages(sorted(set(pages)))
        findings.append(item)

    if reader.is_encrypted:
        add("BLOCKER", "encrypted", "PDF is encrypted or password-protected.")
        return {
            "schema_version": 1,
            "source": str(path.resolve()),
            "sha256": sha256_file(path),
            "pdf_version": version,
            "encrypted": True,
            "findings": findings,
        }

    page_texts: list[str] = []
    blank_pages: list[int] = []
    image_only_pages: list[int] = []
    non_letter_pages: list[int] = []
    rotated_pages: list[int] = []
    page_sizes: Counter[str] = Counter()
    crop_sizes: Counter[str] = Counter()
    cropbox_pages: list[int] = []
    fonts: dict[tuple[str, str], dict[str, Any]] = {}
    links: Counter[str] = Counter()
    total_text_chars = 0

    try:
        labels = list(reader.page_labels)
    except Exception:
        labels = []

    for page_number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        page_texts.append(text)
        chars = len(normalized_text(text))
        total_text_chars += chars
        xobjects = page_xobjects(page)
        stream_length = content_length(page)
        if chars == 0 and not xobjects and stream_length < 20:
            blank_pages.append(page_number)
        if chars < 5 and xobjects.get("/Image", 0) > 0:
            image_only_pages.append(page_number)

        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        page_sizes[f"{width:.1f}x{height:.1f}"] += 1
        crop_width = float(page.cropbox.width)
        crop_height = float(page.cropbox.height)
        crop_sizes[f"{crop_width:.1f}x{crop_height:.1f}"] += 1
        media_letter = (
            abs(width - LETTER[0]) <= LETTER_TOLERANCE
            and abs(height - LETTER[1]) <= LETTER_TOLERANCE
        ) or (
            abs(width - LETTER[1]) <= LETTER_TOLERANCE
            and abs(height - LETTER[0]) <= LETTER_TOLERANCE
        )
        crop_letter = (
            abs(crop_width - LETTER[0]) <= LETTER_TOLERANCE
            and abs(crop_height - LETTER[1]) <= LETTER_TOLERANCE
        ) or (
            abs(crop_width - LETTER[1]) <= LETTER_TOLERANCE
            and abs(crop_height - LETTER[0]) <= LETTER_TOLERANCE
        )
        if not media_letter or not crop_letter:
            non_letter_pages.append(page_number)
        if abs(width - crop_width) > LETTER_TOLERANCE or abs(height - crop_height) > LETTER_TOLERANCE:
            cropbox_pages.append(page_number)
        if int(page.rotation or 0) % 360:
            rotated_pages.append(page_number)

        for font in page_fonts(page):
            key = (font["name"], font["subtype"])
            existing = fonts.setdefault(key, {**font, "pages": []})
            existing["embedded"] = existing["embedded"] or font["embedded"]
            existing["pages"].append(page_number)
        links.update(link_counts(page))

    if version and float(version) > 1.4:
        add("MAJOR", "pdf-version", f"PDF header is {version}; confirm Acrobat 5/PDF 1.4 compatibility.")
    if is_linearized(path):
        add("MINOR", "fast-web-view", "PDF is linearized (Fast Web View); UBC recommends not using it.")
    if blank_pages:
        add("BLOCKER", "blank-pages", "Pages appear blank; UBC does not allow blank pages.", blank_pages)
    if non_letter_pages:
        add("BLOCKER", "non-letter-pages", "Pages are not US Letter portrait or landscape.", non_letter_pages)
    if cropbox_pages:
        add("QUERY", "cropbox-differs", "CropBox differs from MediaBox; confirm that no content is clipped in rendering.", cropbox_pages)
    if image_only_pages:
        severity = "BLOCKER" if len(image_only_pages) / max(len(reader.pages), 1) > 0.8 else "QUERY"
        add(severity, "image-only-pages", "Pages have images but almost no extractable text; confirm they are figures rather than scanned thesis pages.", image_only_pages)
    if total_text_chars < len(reader.pages) * 20:
        add("BLOCKER", "low-text-document", "Document-wide text extraction is unusually low; a scanned PDF may have been supplied.")

    unembedded = [
        font for font in fonts.values() if not font["embedded"] and not font["base14"]
    ]
    if unembedded:
        pages = sorted({page for font in unembedded for page in font["pages"]})
        add("MAJOR", "unembedded-fonts", "Non-standard fonts appear not to be embedded; verify preservation and rendering.", pages)
    if links.get("unresolved"):
        add("QUERY", "unresolved-links", f"Found {links['unresolved']} link annotations without a URI or destination.")

    geometry = (
        {"available": False, "reason": "skipped by command-line option"}
        if skip_geometry else scan_geometry(path, labels, geometry_tolerance, geometry_dpi)
    )
    if not geometry.get("available") and not skip_geometry:
        add("QUERY", "geometry-unavailable", "Page-margin geometry scan was unavailable; do not issue a final GO.")
    if geometry.get("violations"):
        pages = [row["pdf_page"] for row in geometry["violations"]]
        add(
            "QUERY", "margin-overflow",
            "Objects may cross UBC minimum body margins. Render with margin overlays; any confirmed formula, text, figure, or table overflow is a BLOCKER.",
            pages,
        )
    missing_numbers = [
        page for page in geometry.get("missing_visible_page_number_pages", []) if isinstance(page, int)
    ]
    if missing_numbers:
        add("QUERY", "visible-page-number", "Visible printed page label was not located; confirm at high resolution.", missing_numbers)
    close_numbers = [
        page for page in geometry.get("page_number_too_close_pages", []) if isinstance(page, int)
    ]
    if close_numbers:
        add("QUERY", "page-number-edge", "Page number may be closer than 0.5 inch to a page edge.", close_numbers)

    metadata = {str(key).lstrip("/"): str(value) for key, value in (reader.metadata or {}).items()}
    if not metadata.get("Title", "").strip():
        add("MINOR", "missing-metadata-title", "Internal PDF title metadata is empty.")
    if final_name and not FINAL_NAME.fullmatch(path.name):
        add("BLOCKER", "final-filename", "Filename does not match UBC's lowercase final-submission pattern.")

    sections, chapters = detect_sections(page_texts)
    for required in ("abstract", "lay_summary", "preface", "table_of_contents", "bibliography"):
        if required not in sections:
            add("QUERY", f"section-{required}", f"Required section heading '{required}' was not detected; verify manually.")
    if sections.get("abstract") and sections["abstract"] != 3:
        add("QUERY", "abstract-position", "Abstract heading was not detected on PDF page 3; confirm the component order.", [sections["abstract"]])

    word_counts: dict[str, dict[str, Any]] = {}
    if sections.get("abstract") and sections.get("lay_summary"):
        count = section_word_count(
            page_texts, sections["abstract"], sections["lay_summary"],
            SECTION_NAMES["abstract"], SECTION_NAMES["lay_summary"]
        )
        word_counts["abstract"] = {"approximate": count, "limit": 350}
        if count > 350:
            add("QUERY", "abstract-word-count", f"Approximate abstract word count is {count}, above 350; confirm with the source text.", [sections["abstract"]])
    if sections.get("lay_summary") and sections.get("preface"):
        count = section_word_count(
            page_texts, sections["lay_summary"], sections["preface"],
            SECTION_NAMES["lay_summary"], SECTION_NAMES["preface"]
        )
        word_counts["lay_summary"] = {"approximate": count, "limit": 150}
        if count > 150:
            add("QUERY", "lay-summary-word-count", f"Approximate lay summary word count is {count}, above 150; confirm with the source text.", [sections["lay_summary"]])

    try:
        outlines = outline_count(reader.outline)
    except Exception:
        outlines = 0

    font_rows = []
    for font in sorted(fonts.values(), key=lambda row: (row["name"], row["subtype"])):
        font_rows.append({**font, "pages": compact_pages(sorted(set(font["pages"])), 12)})

    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "pdf_version": version,
        "encrypted": False,
        "linearized": is_linearized(path),
        "page_count": len(reader.pages),
        "page_sizes_points": dict(sorted(page_sizes.items())),
        "crop_sizes_points": dict(sorted(crop_sizes.items())),
        "rotated_pages": compact_pages(rotated_pages),
        "blank_pages": compact_pages(blank_pages),
        "image_only_pages": compact_pages(image_only_pages),
        "page_label_segments": label_segments(labels),
        "metadata": metadata,
        "outline_items": outlines,
        "links": dict(links),
        "detected_sections": sections,
        "chapter_openers": compact_pages(sorted(set(chapters))),
        "approximate_word_counts": word_counts,
        "geometry": geometry,
        "fonts": font_rows,
        "findings": findings,
    }
    if compare:
        result["comparison"] = compare_pdf(page_texts, reader, compare)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--json", type=Path, help="Write the complete compact report to this file.")
    parser.add_argument("--compare", type=Path, help="Compare page text and layout with a prior PDF.")
    parser.add_argument("--final-name", action="store_true", help="Enforce the UBC final filename pattern.")
    parser.add_argument("--skip-geometry", action="store_true", help="Skip pdfplumber margin geometry checks.")
    parser.add_argument(
        "--geometry-tolerance", type=float, default=GEOMETRY_TOLERANCE_PT,
        help="Ignore boundary overrun up to this many PDF points (default: 1.5).",
    )
    parser.add_argument(
        "--geometry-dpi", type=int, default=GEOMETRY_RENDER_DPI,
        help="Raster resolution for visible-ink margin checks (default: 96).",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")
    if args.compare and not args.compare.is_file():
        parser.error(f"Baseline PDF not found: {args.compare}")
    if args.geometry_tolerance < 0:
        parser.error("Geometry tolerance must be non-negative.")
    if args.geometry_dpi < 72:
        parser.error("Geometry DPI must be at least 72.")

    report = inspect(
        args.pdf, args.final_name, args.compare,
        args.skip_geometry, args.geometry_tolerance, args.geometry_dpi,
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    counts = Counter(item["severity"] for item in report.get("findings", []))
    codes = ",".join(item["code"] for item in report.get("findings", [])) or "none"
    print(
        f"pages={report.get('page_count', '?')} "
        f"blockers={counts['BLOCKER']} majors={counts['MAJOR']} "
        f"minors={counts['MINOR']} queries={counts['QUERY']} codes={codes}"
    )
    return 2 if counts["BLOCKER"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
