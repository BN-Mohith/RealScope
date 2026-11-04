"""
Shared helpers for the lab-manual extraction scripts.

Every path written to a CSV is stored RELATIVE TO THE REPO ROOT with forward
slashes (e.g. ``Data/raw_data/extracted_images/img_016_01.png``).  That makes
the CSVs portable: copy/clone the repo onto any laptop (Windows, macOS, Linux)
and the links still resolve, because they never contain a machine-specific
absolute path.  Use :func:`resolve_link` to turn a link back into a real path.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

# Scripts/extraction/common.py  ->  repo root is two levels above "scripts"
REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCES_DIR = REPO_ROOT / "Source"
DATA_DIR = REPO_ROOT / "Data" / "raw_data"
PAGES_DIR = DATA_DIR / "extracted_pages"
IMAGES_DIR = DATA_DIR / "extracted_images"
DEFAULT_PDF = SOURCES_DIR / "lab_manual.pdf"
PAGES_MANIFEST = PAGES_DIR / "pages_manifest.csv"
IMAGES_CSV = DATA_DIR / "images_metadata.csv"


def configure_tesseract() -> bool:
    """Point pytesseract at the Tesseract program. Works without PATH changes on
    Windows (default install folders) and honours a TESSERACT_CMD env variable."""
    try:
        import pytesseract
    except ImportError:
        return False
    cmd = os.environ.get("TESSERACT_CMD")
    if not cmd and shutil.which("tesseract") is None and sys.platform.startswith("win"):
        for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                  os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")):
            if os.path.exists(c):
                cmd = c
                break
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def to_link(path: Path) -> str:
    """Absolute/relative path -> portable repo-relative POSIX link."""
    p = Path(path).resolve()
    try:
        rel = p.relative_to(REPO_ROOT)
    except ValueError as e:  # pragma: no cover - guard against misuse
        raise ValueError(f"{p} is outside the repo {REPO_ROOT}") from e
    return str(PurePosixPath(*rel.parts))


def resolve_link(link: str, repo_root: Path | None = None) -> Path:
    """Repo-relative link from a CSV -> real path on *this* machine."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    return root.joinpath(*PurePosixPath(link).parts)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_cli_path(p: str | Path) -> Path:
    """CLI paths may be given relative to the repo root or the current dir."""
    p = Path(p)
    if p.is_absolute():
        return p
    if p.exists():
        return p.resolve()
    return (REPO_ROOT / p).resolve()


def pdf_page_to_bgr(doc, pdf_page: int, dpi: int = 300):
    """Decode one PDF page to a BGR numpy array (embedded scan if possible)."""
    import cv2
    import numpy as np
    import pymupdf

    page = doc[pdf_page - 1]
    imgs = page.get_images(full=True)
    if len(imgs) == 1 and page.rotation == 0:
        info = doc.extract_image(imgs[0][0])
        if info and info.get("image"):
            arr = cv2.imdecode(np.frombuffer(info["image"], np.uint8), cv2.IMREAD_COLOR)
            if arr is not None:
                return arr
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def parse_page_list(spec: str) -> list[int]:
    """'3,4,5,15-17' -> [3, 4, 5, 15, 16, 17] (order kept, duplicates removed)."""
    if not re.fullmatch(r"\s*\d+(\s*-\s*\d+)?(\s*,\s*\d+(\s*-\s*\d+)?)*\s*,?\s*", spec or ""):
        raise ValueError(f"page list '{spec}' not understood - use e.g. 3,4,5 or 15-21 or 3,15-21")
    pages: list[int] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if a > b:
                raise ValueError(f"Bad range '{part}'")
            pages.extend(range(a, b + 1))
        else:
            pages.append(int(part))
    seen, out = set(), []
    for n in pages:
        if n not in seen:
            seen.add(n)
            out.append(n)
    if not out:
        raise ValueError("No page numbers given")
    return out
