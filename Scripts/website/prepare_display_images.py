"""
STEP 5 - make the images the website shows (display copies only - originals untouched).

Reads   Data/raw_data/images_metadata.csv, Data/raw_data/extracted_images/, Data/raw_data/extracted_pages/,
        Source/lab_manual.pdf
Writes  Data/website/img/diagrams/<image_id>.png            straightened + cleaned diagram
        Data/website/img/diagrams/<image_id>_nolabels.png   same diagram with the printed labels removed
                                                            (only for diagrams that have labels)
        Data/website/manual/p001.jpg ... pNNN.jpg            every page of the manual for the in-site reader
        Data/website/manual/exercise_pages.json              which page each "EXERCISE - N" heading is on

What "straightened + cleaned" means
  * The scans are tilted by up to ~1.5 deg. The tilt of each page is measured from the long
    frame lines printed around every page, and each diagram is rotated back by that angle.
  * The faint mirror-image text showing through from the back of the paper is faded to white
    (light greys -> white, dark lines kept). Nothing is drawn or invented.

Label removal (for the "Show labels" tick box)
  * keeps only the drawing area recorded in the CSV (drawing_bbox_*),
  * whitens any words OCR still finds inside it,
  * keeps only the solid body of the drawing, which cuts off most pointer (leader) lines.
  A few short pointer lines that run INSIDE a drawing can remain.

    python Scripts/website/prepare_display_images.py            (skips files that already exist)
    python Scripts/website/prepare_display_images.py --force
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "extraction"))
sys.path.insert(0, str(REPO / "Scripts" / "website"))
from common import configure_tesseract, resolve_link  # noqa: E402
from site_content import GENTLE_LABEL_REMOVAL, SPECIMENS  # noqa: E402

CSV_PATH = REPO / "Data" / "raw_data" / "images_metadata.csv"
PDF_PATH = REPO / "Source" / "lab_manual.pdf"
SITE = REPO / "Data" / "website"
DIAG = SITE / "img" / "diagrams"
MANUAL = SITE / "manual"


# --------------------------------------------------------------------------- straighten
def page_skew_deg(page_path: Path) -> float:
    """Median angle of the long, nearly horizontal/vertical frame lines on the page."""
    g = cv2.imread(str(page_path), cv2.IMREAD_GRAYSCALE)
    if g is None:
        return 0.0
    ink = (g < 120).astype(np.uint8) * 255
    lines = cv2.HoughLinesP(ink, 1, np.pi / 1800, threshold=200,
                            minLineLength=int(g.shape[1] * 0.45), maxLineGap=12)
    angs = []
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(a) < 5:
                angs.append(a)
            elif abs(abs(a) - 90) < 5:
                angs.append(a - np.sign(a) * 90)
    return float(np.median(angs)) if angs else 0.0


def rotate_white(img: np.ndarray, deg: float) -> np.ndarray:
    if abs(deg) < 0.05:
        return img.copy()
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    c, s = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(round(h * s + w * c)), int(round(h * c + w * s))
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))


_LUT = np.array([255 if v / 185 >= 1 else round(255 * (v / 185) ** 1.8) for v in range(256)], np.uint8)


def clean(img: np.ndarray) -> np.ndarray:
    """Fade paper show-through: greys lighter than ~185 become white, dark ink is kept."""
    return cv2.LUT(img, _LUT)


# --------------------------------------------------------------------------- labels off
def _k(n: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))


def _fill_holes(m: np.ndarray) -> np.ndarray:
    h, w = m.shape
    ff = m.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if ff[y, x] == 0:
            cv2.floodFill(ff, mask, (x, y), 2)
    return np.where(ff == 2, 0, 1).astype(np.uint8)


def remove_labels(img: np.ndarray, row: dict, ocr_ok: bool, gentle: bool) -> np.ndarray:
    H, W = img.shape[:2]
    cw, ch = int(float(row["crop_width_px"])), int(float(row["crop_height_px"]))
    ox, oy = (W - cw) / 2, (H - ch) / 2  # rotation enlarged the canvas evenly on each side
    bx, by = float(row["bbox_x0"]), float(row["bbox_y0"])
    x0 = max(0, int(float(row["drawing_bbox_x0"]) - bx + ox) - 3)
    y0 = max(0, int(float(row["drawing_bbox_y0"]) - by + oy) - 3)
    x1 = min(W, int(float(row["drawing_bbox_x1"]) - bx + ox) + 3)
    y1 = min(H, int(float(row["drawing_bbox_y1"]) - by + oy) + 3)
    out = np.full_like(img, 255)
    out[y0:y1, x0:x1] = img[y0:y1, x0:x1]

    if ocr_ok:
        import pytesseract
        big = cv2.resize(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        d = pytesseract.image_to_data(big, config="--psm 11", output_type=pytesseract.Output.DICT)
        for i, t in enumerate(d["text"]):
            t = t.strip()
            if sum(c.isalpha() for c in t) >= 3 and float(d["conf"][i]) >= 55:
                a, b, w, h = (v // 2 for v in (d["left"][i], d["top"][i], d["width"][i], d["height"][i]))
                if h <= 40:
                    out[max(0, b - 2):b + h + 2, max(0, a - 2):a + w + 2] = 255

    close_k, open_k, grow_k = (15, 13, 5) if gentle else (9, 11, 3)
    g = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    m = cv2.morphologyEx((g < 170).astype(np.uint8), cv2.MORPH_CLOSE, _k(close_k))
    m = _fill_holes(m)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, _k(open_k))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        big = st[1:, cv2.CC_STAT_AREA].max()
        keep = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.12 * big])
    else:
        keep = m > 0
    keep = cv2.dilate(keep.astype(np.uint8), _k(grow_k)) > 0
    out[~keep] = 255
    return out


# --------------------------------------------------------------------------- manual pages
def render_manual(force: bool) -> int:
    import hashlib
    import pymupdf
    MANUAL.mkdir(parents=True, exist_ok=True)
    stamp = MANUAL / ".source_pdf.sha256"
    pdf_sha = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
    if stamp.exists() and stamp.read_text().strip() != pdf_sha:
        force = True  # a different PDF: render everything again
        for old in MANUAL.glob("p*.jpg"):
            old.unlink()
        (MANUAL / "exercise_pages.json").unlink(missing_ok=True)
    doc = pymupdf.open(str(PDF_PATH))
    made = 0
    for i, page in enumerate(doc):
        dest = MANUAL / f"p{i + 1:03d}.jpg"
        if dest.exists() and not force:
            continue
        pix = page.get_pixmap(dpi=120)
        pix.save(str(dest), jpg_quality=72)
        made += 1
    for extra in MANUAL.glob("p*.jpg"):  # pages beyond the end of a shorter PDF
        if int(extra.stem[1:]) > doc.page_count:
            extra.unlink()
    stamp.write_text(pdf_sha)
    print(f"  manual pages   : {doc.page_count} ({made} new)  -> {MANUAL}")
    find_exercise_pages(doc, force)
    return doc.page_count


def find_exercise_pages(doc, force: bool) -> None:
    """OCR the top of every page for the 'EXERCISE - N' banner, so the website's
    manual reader can jump to the start of each exercise."""
    import json
    import re
    dest = MANUAL / "exercise_pages.json"
    if dest.exists() and not force:
        return
    if not configure_tesseract():
        print("  (Tesseract not found - exercise buttons will jump to the first diagram page instead)")
        return
    import pytesseract
    found = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=110)
        im = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        g = cv2.cvtColor(im[:, :, :3], cv2.COLOR_RGB2GRAY)[: int(pix.height * 0.32)]
        g = np.where(g < 70, 0, 255).astype(np.uint8)  # banner ink only - ignores show-through
        txt = pytesseract.image_to_string(g, config="--psm 6").upper()
        m = re.search(r"EXERC[I1L]SE\s*[-\u2013:.]?\s*([0-9]{1,2})\b", txt)
        if m:
            found.append([i + 1, int(m.group(1))])
    # drop misreads that break the increasing order (e.g. a 3 read as 8)
    clean = [f for k, f in enumerate(found) if k + 1 >= len(found) or f[1] < found[k + 1][1]]
    dest.write_text(json.dumps({"starts": clean}), encoding="utf-8")
    print(f"  exercise pages : {len(clean)} exercise headings found")


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="remake files that already exist")
    args = ap.parse_args()
    if not CSV_PATH.exists():
        sys.exit("[X] images_metadata.csv not found - run the extraction (steps 1-2) first.")
    DIAG.mkdir(parents=True, exist_ok=True)
    ocr_ok = configure_tesseract()
    if not ocr_ok:
        print("  (Tesseract not found - label removal will skip the word-whitening part)")

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["image_type"] == "figure"]
    skews: dict[str, float] = {}
    n_d = n_l = 0
    for r in rows:
        iid = r["image_id"]
        dst = DIAG / f"{iid}.png"
        dst_nl = DIAG / f"{iid}_nolabels.png"
        has_labels = bool(SPECIMENS.get(iid, {}).get("labels"))
        src_crop = resolve_link(r["image_link"])
        fresh = dst.exists() and src_crop.exists() and dst.stat().st_mtime >= src_crop.stat().st_mtime
        if fresh and (dst_nl.exists() or not has_labels) and not args.force:
            continue
        page = resolve_link(r["page_image_link"])
        if r["page_image_link"] not in skews:
            skews[r["page_image_link"]] = page_skew_deg(page)
        crop = cv2.imread(str(src_crop), cv2.IMREAD_COLOR)
        if crop is None:
            print(f"  [X] cannot read {r['image_link']}")
            continue
        disp = clean(rotate_white(crop, skews[r["page_image_link"]]))
        cv2.imwrite(str(dst), disp)
        n_d += 1
        if has_labels:
            cv2.imwrite(str(dst_nl), remove_labels(disp, r, ocr_ok, iid in GENTLE_LABEL_REMOVAL))
            n_l += 1
    wanted = {f"{r['image_id']}.png" for r in rows} | {f"{r['image_id']}_nolabels.png" for r in rows}
    for old in DIAG.glob("*.png"):
        if old.name not in wanted:
            old.unlink()
    for link, a in sorted(skews.items()):
        print(f"  tilt corrected : {Path(link).name}  {a:+.2f} deg")
    print(f"  diagrams       : {n_d} made, {n_l} label-free copies  -> {DIAG}")
    if PDF_PATH.exists():
        render_manual(args.force)
    else:
        print(f"  [X] {PDF_PATH} missing - the website's lab-manual reader will be empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
