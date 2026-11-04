"""
STEP 1 - Extract selected pages from the lab manual (lossless).

Inputs
  --pdf      the full lab manual (default: Source/lab_manual.pdf)
  --pages    page numbers that contain microscopic images, e.g. "3,4,5,15-17"
  --numbering  "printed" (the number printed at the bottom of the manual page)
               or "pdf" (the page index shown by a PDF viewer). In this manual
               printed = pdf - 1, which is detected/verified automatically.

Output (in Data/raw_data/extracted_pages/)
  page_XXX.jpg          one file per requested page (XXX = PDF page number)
  pages_manifest.csv    one row per page -> used by extract_images_from_pages.py

Quality
  The manual is a scan: each PDF page is one embedded JPEG.  We copy those
  JPEG bytes out *unchanged* (byte-for-byte identical to what is inside the
  PDF - no decoding, no re-compression, no resizing).  Only if a page is not a
  single full-page image do we fall back to rendering it at --dpi as PNG.

Example
  python Scripts/extraction/extract_pages.py --pages 3,4,5,7,11,15,17,19,21,31,33,35,37,39,41 --numbering printed
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep scripts/ free of __pycache__ folders

import pymupdf  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DEFAULT_PDF, PAGES_DIR, PAGES_MANIFEST, configure_tesseract, parse_page_list,
    resolve_cli_path, sha256_of, to_link,
)

MANIFEST_FIELDS = [
    "pdf_page", "printed_page", "printed_page_ocr_check", "page_image_link",
    "width_px", "height_px", "extraction_method", "page_image_sha256",
    "source_pdf_link", "source_pdf_sha256",
]


# --------------------------------------------------------------------------
# printed page number (footer) via OCR - used only to VERIFY the numbering
# --------------------------------------------------------------------------
def ocr_footer_number(doc: pymupdf.Document, pdf_page: int) -> int | None:
    if not configure_tesseract():
        return None
    import cv2
    import numpy as np
    import pytesseract
    page = doc[pdf_page - 1]
    pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    h, w = img.shape
    strip = img[int(h * 0.92):int(h * 0.995), int(w * 0.40):int(w * 0.60)]  # page number, bottom centre
    strip = np.where(strip < 110, 0, 255).astype(np.uint8)
    strip = cv2.resize(strip, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    try:
        txt = pytesseract.image_to_string(
            strip, config="--psm 6 -c tessedit_char_whitelist=0123456789")
    except Exception:
        return None
    nums = [int(n) for n in re.findall(r"\d{1,3}", txt) if 0 < int(n) <= len(doc)]
    return nums[-1] if nums else None


def detect_offset(doc: pymupdf.Document, sample=(10, 20, 30, 40, 50)) -> tuple[int, int]:
    """Return (offset, votes) where printed = pdf - offset, by OCR of footers."""
    votes: dict[int, int] = {}
    for p in sample:
        if p > len(doc):
            continue
        n = ocr_footer_number(doc, p)
        if n is not None:
            votes[p - n] = votes.get(p - n, 0) + 1
    if not votes:
        return 1, 0
    off = max(votes, key=votes.get)
    return off, votes[off]


# --------------------------------------------------------------------------
# lossless page extraction
# --------------------------------------------------------------------------
def extract_page(doc: pymupdf.Document, pdf_page: int, out_dir: Path, dpi: int) -> tuple[Path, str, int, int]:
    page = doc[pdf_page - 1]
    images = page.get_images(full=True)
    page_area = page.rect.width * page.rect.height
    stem = out_dir / f"page_{pdf_page:03d}"

    if len(images) == 1 and page.rotation == 0:
        xref = images[0][0]
        rects = page.get_image_rects(xref)
        covers = rects and (rects[0].width * rects[0].height) >= 0.50 * page_area
        info = doc.extract_image(xref)
        # only take the raw bytes if they're a normal, upright, full-page image
        if covers and info and info.get("ext") in ("jpeg", "jpg", "png", "jp2", "tiff"):
            ext = "jpg" if info["ext"] in ("jpeg", "jpg") else info["ext"]
            path = stem.with_suffix(f".{ext}")
            path.write_bytes(info["image"])  # byte-identical copy
            return path, "embedded_original_bytes", info["width"], info["height"]

    # fallback: lossless PNG render of the page
    pix = page.get_pixmap(dpi=dpi)
    path = stem.with_suffix(".png")
    pix.save(path)
    return path, f"rendered_png_{dpi}dpi", pix.width, pix.height


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", default=str(DEFAULT_PDF), help="full lab manual PDF (raw source)")
    ap.add_argument("--pages", required=True, help='pages with microscopic images, e.g. "3,4,5,15-17"')
    ap.add_argument("--numbering", choices=["printed", "pdf"], default="pdf",
                    help="how --pages is numbered (default: pdf)")
    ap.add_argument("--offset", type=int, default=None,
                    help="printed = pdf - offset. Default: auto-detected from page footers")
    ap.add_argument("--out", default=str(PAGES_DIR), help="output folder")
    ap.add_argument("--dpi", type=int, default=300, help="DPI for the render fallback only")
    ap.add_argument("--keep-old", action="store_true",
                    help="do not delete previous page_*.jpg/png outputs first")
    args = ap.parse_args()

    pdf_path = resolve_cli_path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1
    out_dir = resolve_cli_path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.keep_old:
        for old in list(out_dir.glob("page_*.*")):
            old.unlink()

    try:
        requested = parse_page_list(args.pages)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    doc = pymupdf.open(pdf_path)
    if args.offset is None:
        offset, votes = detect_offset(doc)
        print(f"[info] printed = pdf - {offset}  (auto-detected from {votes} page footer(s))")
    else:
        offset = args.offset
        print(f"[info] printed = pdf - {offset}  (given)")

    pdf_pages = [n + offset if args.numbering == "printed" else n for n in requested]
    bad = [n for n in pdf_pages if not 1 <= n <= len(doc)]
    if bad:
        print(f"ERROR: PDF pages {bad} out of range 1..{len(doc)}", file=sys.stderr)
        return 1

    src_sha = sha256_of(pdf_path)
    try:
        src_link = to_link(pdf_path)
    except ValueError:
        src_link = str(pdf_path)

    rows = []
    for req, pdf_page in zip(requested, pdf_pages):
        path, method, w, h = extract_page(doc, pdf_page, out_dir, args.dpi)
        printed = pdf_page - offset
        ocr_n = ocr_footer_number(doc, pdf_page)
        if ocr_n is not None and len(str(ocr_n)) != len(str(printed)):
            ocr_n = None  # only part of the number was read (e.g. '1' of '21') -> treat as unread
        check = "not_read" if ocr_n is None else ("match" if ocr_n == printed else f"mismatch(ocr={ocr_n})")
        rows.append({
            "pdf_page": pdf_page, "printed_page": printed, "printed_page_ocr_check": check,
            "page_image_link": to_link(path), "width_px": w, "height_px": h,
            "extraction_method": method, "page_image_sha256": sha256_of(path),
            "source_pdf_link": src_link, "source_pdf_sha256": src_sha,
        })
        print(f"  printed p{printed:>3} | pdf p{pdf_page:>3} -> {to_link(path)}  "
              f"[{w}x{h}, {method}, footer {check}]")

    with open(resolve_cli_path(args.out) / PAGES_MANIFEST.name, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        wr.writeheader()
        wr.writerows(rows)
    print(f"[done] {len(rows)} page(s) -> {to_link(out_dir)}/ ; manifest: "
          f"{to_link(out_dir / PAGES_MANIFEST.name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
