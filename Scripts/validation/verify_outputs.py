"""
STEP 3 (check) - Prove the outputs of steps 1 and 2 are correct. Run it in a demo.

Checks
  Pages (Data/raw_data/extracted_pages/pages_manifest.csv)
    * every page file exists and its SHA-256 matches the manifest
    * pages taken as 'embedded_original_bytes' are byte-for-byte identical to the
      scan stored inside Source/lab_manual.pdf  (=> no quality loss)
  Images (Data/raw_data/images_metadata.csv)
    * every image_link is a portable relative link (no C:\\..., no /home/...)
      and opens on this machine
    * SHA-256 of each image matches the CSV
    * crop size == bounding box size, and the crop's pixels are IDENTICAL to the
      page pixels inside that bounding box (=> nothing re-drawn / resized / invented)
    * bbox lies inside the page, normalised bbox agrees with pixel bbox
    * every group_id points to an existing group image
  Optional: --sheet writes a contact sheet of every crop + caption for eyeballing.

Example
  python Scripts/validation/verify_outputs.py --sheet
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

import cv2  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
from common import (  # noqa: E402
    DATA_DIR, IMAGES_CSV, PAGES_MANIFEST, resolve_link, sha256_of,
)


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def is_portable(link: str) -> bool:
    return bool(link) and not link.startswith(("/", "\\")) and ":" not in link and "\\" not in link \
        and ".." not in PurePosixPath(link).parts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", action="store_true", help="also write review_overlays/contact_sheet.jpg")
    args = ap.parse_args()
    errors: list[str] = []

    # ------------------------------------------------------------------ pages
    if not PAGES_MANIFEST.exists():
        print(f"FAIL: {PAGES_MANIFEST} missing - run extract_pages.py first")
        return 1
    pages = read_csv(PAGES_MANIFEST)
    doc = None
    try:
        import pymupdf
        src = resolve_link(pages[0]["source_pdf_link"])
        if src.exists():
            doc = pymupdf.open(src)
            if sha256_of(src) != pages[0]["source_pdf_sha256"]:
                errors.append("source PDF changed since pages were extracted (sha256 differs)")
    except Exception as e:  # pragma: no cover
        errors.append(f"cannot open source PDF: {e}")
    page_imgs = {}
    identical = 0
    for pg in pages:
        link = pg["page_image_link"]
        path = resolve_link(link)
        if not is_portable(link):
            errors.append(f"page link not portable: {link}")
        if not path.exists():
            errors.append(f"missing page image {link}")
            continue
        if sha256_of(path) != pg["page_image_sha256"]:
            errors.append(f"sha256 mismatch for {link}")
        if doc is not None and pg["extraction_method"] == "embedded_original_bytes":
            page = doc[int(pg["pdf_page"]) - 1]
            raw = doc.extract_image(page.get_images(full=True)[0][0])["image"]
            if raw == path.read_bytes():
                identical += 1
            else:
                errors.append(f"{link} is not byte-identical to the scan inside the PDF")
        page_imgs[link] = cv2.imread(str(path), cv2.IMREAD_COLOR)
    print(f"[pages ] {len(pages)} page(s); {identical} byte-identical to the original scans in the PDF")

    # ------------------------------------------------------------------ images
    if not IMAGES_CSV.exists():
        print(f"FAIL: {IMAGES_CSV} missing - run extract_images_from_pages.py first")
        return 1
    rows = read_csv(IMAGES_CSV)
    groups = {r["image_id"] for r in rows if r["image_type"] == "group"}
    pixel_exact = 0
    for r in rows:
        link = r["image_link"]
        if not is_portable(link):
            errors.append(f"{r['image_id']}: link not portable: {link}")
            continue
        path = resolve_link(link)
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            errors.append(f"{r['image_id']}: cannot open {link}")
            continue
        if sha256_of(path) != r["image_sha256"]:
            errors.append(f"{r['image_id']}: sha256 mismatch")
        x0, y0, x1, y1 = (int(r[k]) for k in ("bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1"))
        W, H = int(r["page_width_px"]), int(r["page_height_px"])
        if not (0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H):
            errors.append(f"{r['image_id']}: bbox outside page")
        if (img.shape[1], img.shape[0]) != (x1 - x0, y1 - y0):
            errors.append(f"{r['image_id']}: crop size != bbox size")
        if abs(float(r["bbox_norm_x0"]) - x0 / W) > 1e-4 or abs(float(r["bbox_norm_y1"]) - y1 / H) > 1e-4:
            errors.append(f"{r['image_id']}: normalised bbox inconsistent")
        page = page_imgs.get(r["page_image_link"])
        if page is not None:
            if np.array_equal(page[y0:y1, x0:x1], img):
                pixel_exact += 1
            else:
                errors.append(f"{r['image_id']}: pixels differ from the page inside the bbox")
        if r["image_type"] == "figure" and r["group_id"] and r["group_id"] not in groups:
            errors.append(f"{r['image_id']}: group {r['group_id']} has no group image")
    figs = [r for r in rows if r["image_type"] == "figure"]
    print(f"[images] {len(figs)} figure(s) + {len(groups)} group(s); "
          f"{pixel_exact}/{len(rows)} crops pixel-identical to the page inside their bbox")
    print(f"[text  ] captions: {sum(bool(r['caption']) for r in figs)}/{len(figs)}   "
          f"manual explanation found: {sum(bool(r['manual_text']) for r in figs)}/{len(figs)}   "
          f"flagged needs_review: {sum(bool(r['needs_review']) for r in figs)}")

    # ------------------------------------------------------------------ contact sheet
    if args.sheet:
        cell_w, cell_h, cols = 300, 280, 6
        tiles = []
        for r in figs:
            img = cv2.imread(str(resolve_link(r["image_link"])))
            s = min((cell_w - 10) / img.shape[1], (cell_h - 50) / img.shape[0])
            img = cv2.resize(img, (max(1, int(img.shape[1] * s)), max(1, int(img.shape[0] * s))),
                             interpolation=cv2.INTER_AREA)  # thumbnail for viewing only
            tile = np.full((cell_h, cell_w, 3), 255, np.uint8)
            tile[5:5 + img.shape[0], 5:5 + img.shape[1]] = img
            cv2.putText(tile, f"{r['image_id']}  p{r['printed_page']}", (5, cell_h - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 200), 1, cv2.LINE_AA)
            cv2.putText(tile, (r["caption"] or "(no caption)")[:40], (5, cell_h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(tile)
        while len(tiles) % cols:
            tiles.append(np.full((cell_h, cell_w, 3), 255, np.uint8))
        sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
        out = DATA_DIR / "review_overlays" / "contact_sheet.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f"[sheet ] {out.relative_to(DATA_DIR.parents[1]).as_posix()}")

    if errors:
        print(f"\nFAIL - {len(errors)} problem(s):")
        for e in errors[:50]:
            print("  -", e)
        return 1
    print("\nPASS - all checks succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
