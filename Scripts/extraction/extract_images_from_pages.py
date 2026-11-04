"""
STEP 2 - Cut the microscopic-image figures out of the extracted pages and
build a CSV (links + descriptions + bounding boxes + page numbers).

Input
  Data/raw_data/extracted_pages/pages_manifest.csv   (written by extract_pages.py)
  ...and the page images it points to. The source PDF (Source/lab_manual.pdf)
  is opened read-only to pick up the exercise title and the manual's own
  explanation text for each figure.

Output (in Data/raw_data/)
  extracted_images/img_PPP_NN.png   one crop per individual figure (drawing + its labels)
  extracted_images/grp_PPP_N.png    one crop per group of related figures
                                    (e.g. all mitosis stages on one page)
  images_metadata.csv               one row per saved image -> used by the next script
  review_overlays/page_PPP.jpg      page with every detected box drawn on it (for checking)

How it works (no generative AI - every value comes from the page itself)
  1. Ink = pixels darker than --ink-threshold. This drops the faint mirror-image
     text that shows through from the back of each scanned page.
  2. The printed page frame and table grid lines are removed (long thin lines).
  3. Tesseract OCR finds every word; low-confidence / junk "words" are dropped.
  4. What is left after removing text = drawings. Each connected drawing is a figure.
  5. Text attached to a figure by a leader line = its labels.
     Un-attached text directly under a figure = its caption.
     Un-attached text under several figures (e.g. "STAGES OF MEIOSIS - I") = a group title.
  6. Pages with 3+ figures and no printed group title are grouped under the exercise title.
  7. Crops are cut from the ORIGINAL page pixels and saved as PNG (lossless) -
     no resizing, no re-compression, no enhancement.
  8. The figure's explanation is looked up in the manual's own text pages for
     that exercise (OCR) by matching the caption to a heading; if there is no
     confident match the cell is left empty rather than guessed.

Example
  python Scripts/extraction/extract_images_from_pages.py
"""
from __future__ import annotations

import argparse
import csv
import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True  # keep scripts/ free of __pycache__ folders

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytesseract  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DATA_DIR, IMAGES_CSV, IMAGES_DIR, PAGES_MANIFEST, configure_tesseract, pdf_page_to_bgr,
    resolve_cli_path, resolve_link, sha256_of, to_link,
)

OCR_SCALE = 3  # OCR runs on a 3x upscaled COPY; crops always use original pixels

CSV_FIELDS = [
    "image_id", "image_type", "group_id", "image_link", "page_image_link",
    "pdf_page", "printed_page", "exercise_title", "caption", "group_title",
    "labels", "manual_text", "manual_text_printed_page", "description",
    "bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1",
    "bbox_norm_x0", "bbox_norm_y0", "bbox_norm_x1", "bbox_norm_y1",
    "drawing_bbox_x0", "drawing_bbox_y0", "drawing_bbox_x1", "drawing_bbox_y1",
    "page_width_px", "page_height_px", "crop_width_px", "crop_height_px",
    "caption_ocr_conf", "needs_review", "image_sha256",
]


# =============================================================================
# small geometry helpers
# =============================================================================
def box_union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def x_overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0]))


def clamp_box(b, W, H):
    return [max(0, int(b[0])), max(0, int(b[1])), min(W, int(b[2])), min(H, int(b[3]))]


# =============================================================================
# OCR
# =============================================================================
def ocr_words(gray_clean: np.ndarray, psm: int = 11) -> list[dict]:
    up = cv2.resize(gray_clean, None, fx=OCR_SCALE, fy=OCR_SCALE, interpolation=cv2.INTER_CUBIC)
    d = pytesseract.image_to_data(up, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d["text"]):
        t = (t or "").strip()
        conf = float(d["conf"][i])
        if not t or conf < 0:
            continue
        x, y, w, h = (int(round(d[k][i] / OCR_SCALE)) for k in ("left", "top", "width", "height"))
        out.append(dict(text=t, conf=conf, x0=x, y0=y, x1=x + w, y1=y + h))
    return out


def group_into_lines(words: list[dict]) -> list[dict]:
    words = sorted(words, key=lambda w: ((w["y0"] + w["y1"]) / 2, w["x0"]))
    lines: list[dict] = []
    for w in words:
        wh = w["y1"] - w["y0"]
        target = None
        for L in lines:
            lh = L["y1"] - L["y0"]
            ov = min(L["y1"], w["y1"]) - max(L["y0"], w["y0"])
            if ov < 0.5 * min(lh, wh):
                continue
            gap = w["x0"] - L["words"][-1]["x1"]
            hh = max(lh, wh)
            if -hh < gap < 1.6 * hh:
                target = L
                break
        if target is None:
            lines.append(dict(words=[w], x0=w["x0"], y0=w["y0"], x1=w["x1"], y1=w["y1"]))
        else:
            target["words"].append(w)
            for k, f in (("x0", min), ("y0", min), ("x1", max), ("y1", max)):
                target[k] = f(target[k], w[k])
    for L in lines:
        L["words"].sort(key=lambda w: w["x0"])
        L["text"] = " ".join(w["text"] for w in L["words"])
        L["conf"] = float(np.mean([w["conf"] for w in L["words"]]))
        L["box"] = [L["x0"], L["y0"], L["x1"], L["y1"]]
    return lines


def is_real_text_line(L: dict) -> bool:
    """Reject OCR 'words' that are really bits of drawing (no hallucinated labels)."""
    alpha = sum(c.isalpha() for c in L["text"])
    good_words = sum(1 for w in L["words"] if sum(c.isalpha() for c in w["text"]) >= 3 and w["conf"] >= 60)
    if good_words >= 1 and L["conf"] >= 60:
        return True
    return alpha >= 2 and L["conf"] >= 85 and len(L["words"]) >= 2


def clean_text(s: str) -> str:
    s = s.replace("|", "I").replace("’", "'").replace("‘", "'").replace("”", '"').replace("“", '"')
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^[\s,;:\-_=~—–'\"`!.»>*]+", "", s)        # leading leader-line dashes / quotes
    s = re.sub(r"[\s,;:\-_=~—–'\"`!»>*]+$", "", s)         # trailing ones (keeps ')' and '.')
    return s.strip()


# =============================================================================
# page analysis
# =============================================================================
@dataclass
class Figure:
    draw_box: list
    pixel_mask: np.ndarray | None = None  # bool mask (page size) of this figure's drawing ink
    caption_lines: list = field(default_factory=list)
    label_lines: list = field(default_factory=list)
    group: int | None = None
    crop_labels: list | None = None
    label_texts: list = field(default_factory=list)

    @property
    def cx(self):
        return (self.draw_box[0] + self.draw_box[2]) / 2

    def crop_box(self):
        b = list(self.draw_box)
        for L in (self.crop_labels if self.crop_labels is not None else self.label_lines):
            b = box_union(b, L["box"])
        if self.caption_lines:  # stray caption letters can extend the drawing: stop above the caption
            cap_top = min(L["y0"] for L in self.caption_lines)
            if self.draw_box[1] + 0.5 * (self.draw_box[3] - self.draw_box[1]) < cap_top < b[3]:
                b[3] = cap_top - 2
        return b

    caption_text: str = ""
    caption_conf: float | None = None

    def caption(self):
        return self.caption_text


def remove_long_lines(ink: np.ndarray):
    """Masks of long thin straight lines (page frame, table grid); tolerant to scan skew."""
    H, W = ink.shape
    seg = max(15, int(W * 0.06))
    out = {}
    for horiz in (True, False):
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (seg, 1) if horiz else (1, seg))
        m = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k)
        joined = cv2.dilate(m, np.ones((5, 25) if horiz else (25, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(joined, 8)
        keep = np.zeros_like(m)
        boxes = []
        for i in range(1, n):
            length = st[i, 2] if horiz else st[i, 3]
            comp = (lab == i) & (m > 0)
            thick = comp.sum() / max(length, 1)
            if length >= 0.35 * (W if horiz else H) and thick <= 12:
                keep[comp] = 255
                boxes.append([st[i, 0], st[i, 1], st[i, 0] + st[i, 2], st[i, 1] + st[i, 3]])
        out["h" if horiz else "v"] = (keep, boxes)
    return out


def find_frame(lines, W, H):
    fx0, fy0, fx1, fy1 = 0, 0, W, H
    for b in lines["v"][1]:
        if b[2] < W * 0.12:
            fx0 = max(fx0, b[2] + 2)
        if b[0] > W * 0.88:
            fx1 = min(fx1, b[0] - 2)
    for b in lines["h"][1]:
        if b[3] < H * 0.15:
            fy0 = max(fy0, b[3] + 2)
        if b[1] > H * 0.85:
            fy1 = min(fy1, b[1] - 2)
    return [fx0, fy0, fx1, fy1]


def data_table_region(lines, frame, H):
    """Region of a data/observation table (many closely spaced long horizontal lines)."""
    hs = sorted(b for b in lines["h"][1]
                if b[1] > frame[1] + 5 and b[3] < frame[3] - 5)
    if len(hs) < 3:
        return None
    ys = [(b[1] + b[3]) / 2 for b in hs]
    gaps = np.diff(ys)
    if len(gaps) and np.median(gaps) < 0.08 * H:  # spans the frame width (lines may be broken)
        return [frame[0], min(b[1] for b in hs), frame[2], max(b[3] for b in hs)]
    return None


def analyse_page(bgr: np.ndarray, ink_t: int):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    ink = ((gray < ink_t) * 255).astype(np.uint8)
    clean = np.where(gray < ink_t, gray, 255).astype(np.uint8)

    lines = remove_long_lines(ink)
    frame = find_frame(lines, W, H)
    table = data_table_region(lines, frame, H)

    words = [w for w in ocr_words(clean)
             if w["conf"] >= 55 and any(c.isalnum() for c in w["text"]) and (w["y1"] - w["y0"]) <= 0.08 * H]
    text_lines = [L for L in group_into_lines(words) if is_real_text_line(L)]
    fx0, fy0, fx1, fy1 = frame
    text_lines = [L for L in text_lines if fx0 <= (L["x0"] + L["x1"]) / 2 <= fx1
                  and fy0 <= (L["y0"] + L["y1"]) / 2 <= fy1]

    # ---- drawing mask = ink - long lines - text - outside frame
    draw = ink.copy()
    draw[cv2.dilate(cv2.bitwise_or(lines["h"][0], lines["v"][0]), np.ones((5, 5), np.uint8)) > 0] = 0
    for L in text_lines:
        for w in L["words"]:
            draw[max(0, w["y0"] - 1):w["y1"] + 2, max(0, w["x0"] - 1):w["x1"] + 2] = 0
    outside = np.ones_like(draw, dtype=bool)
    outside[fy0:fy1, fx0:fx1] = False
    draw[outside] = 0
    # leader lines are thin and often lighter than solid ink (grey 120-170 on these scans);
    # show-through from the back of the page is lighter still (>190)
    leader_ink = (gray < 175) & (draw > 0) | ((gray < 175) & (gray >= ink_t))
    for L in text_lines:
        for w in L["words"]:
            leader_ink[max(0, w["y0"] - 1):w["y1"] + 2, max(0, w["x0"] - 1):w["x1"] + 2] = False
    leader_ink[outside] = False

    k = max(5, int(W * 0.010))
    closed = cv2.morphologyEx(draw, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(closed, 8)
    comps = []  # [box, set(label ids)]
    for i in range(1, n):
        x, y, w, h, _a = st[i]
        if w * h >= 0.004 * W * H and min(w, h) >= 0.03 * W:
            comps.append([[x, y, x + w, y + h], {i}])
    merged = True
    while merged:  # merge touching / overlapping boxes
        merged = False
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                a, b = comps[i][0], comps[j][0]
                if a[0] - k < b[2] and b[0] - k < a[2] and a[1] - k < b[3] and b[1] - k < a[3]:
                    comps[i] = [box_union(a, b), comps[i][1] | comps[j][1]]
                    comps.pop(j)
                    merged = True
                    break
            if merged:
                break
    if table is not None:  # drop handwriting / numbers inside observation tables
        comps = [c for c in comps if not (table[0] <= (c[0][0] + c[0][2]) / 2 <= table[2]
                                          and table[1] <= (c[0][1] + c[0][3]) / 2 <= table[3])]

    if table is not None:  # table text is neither a label nor a caption
        text_lines = [L for L in text_lines if not (table[1] <= (L["y0"] + L["y1"]) / 2 <= table[3])]

    figs = []
    for box, ids in comps:
        mask = np.isin(lab, list(ids)) & (draw > 0)
        figs.append(Figure(draw_box=box, pixel_mask=mask))

    hs = [L["y1"] - L["y0"] for L in text_lines]
    h_med = float(np.median(hs)) if hs else 12.0
    return dict(W=W, H=H, h_med=h_med, ink_t=ink_t, gray=gray, clean=clean, draw=draw, leader_ink=leader_ink, frame=frame, table=table, text_lines=text_lines, figs=figs, k=k)


# -----------------------------------------------------------------------------
def mark_bold(page):
    """Stroke weight of every text line = share of its ink that survives a 3x3
    erosion (bold strokes survive, regular ones mostly don't)."""
    ink = (page["gray"] < page["ink_t"]).astype(np.uint8)
    for L in page["text_lines"]:
        x0, y0, x1, y1 = L["box"]
        sub = ink[y0:y1, x0:x1]
        a = int(sub.sum())
        L["weight"] = float(cv2.erode(sub, np.ones((3, 3), np.uint8)).sum() / a) if a else 0.0


def _dist_box(a, b):
    dx = max(0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0, max(a[1], b[1]) - min(a[3], b[3]))
    return max(dx, dy)


def _centred_below(L, f, H):
    b = f.draw_box
    lcx = (L["x0"] + L["x1"]) / 2
    return L["y0"] >= b[3] - 0.01 * H and abs(lcx - f.cx) < 0.3 * (b[2] - b[0])


def attach_lines(page) -> list[dict]:
    """Labels = text tied to a figure by a leader line or sitting inside it.
    Everything else is returned as a caption/title candidate (decided later)."""
    W, H, figs = page["W"], page["H"], page["figs"]
    if not page["text_lines"] or "weight" not in page["text_lines"][0]:
        mark_bold(page)
    m = max(3, int(W * 0.006))
    owner = np.zeros((H, W), np.int32)
    for i, f in enumerate(figs):
        owner[f.pixel_mask] = i + 1
        f.label_lines = []
    attached = []
    for L in page["text_lines"]:
        x0, y0, x1, y1 = L["box"]
        ring = owner[max(0, y0 - m):min(H, y1 + m), max(0, x0 - m):min(W, x1 + m)]
        vals, counts = np.unique(ring[ring > 0], return_counts=True)
        best = int(vals[np.argmax(counts)]) - 1 if len(vals) and counts.max() >= 3 else None
        if best is None:
            for i, f in enumerate(figs):
                b = f.draw_box
                if b[0] <= (x0 + x1) / 2 <= b[2] and b[1] <= (y0 + y1) / 2 <= b[3]:
                    best = i
                    break
        attached.append(best)
    all_w = [L["weight"] for L in page["text_lines"]]
    page["bold_t"] = min(0.2, max(0.09, 2 * float(np.median(all_w)) + 0.03)) if all_w else 0.09
    free = []
    for L, o in zip(page["text_lines"], attached):
        L["bold"] = L["weight"] >= page["bold_t"]
        # (stray caption letters OCR missed can extend the drawing box slightly downwards)
        below = o is not None and L["y0"] >= figs[o].draw_box[3] - 2 * page["h_med"]
        if o is not None and not (L["bold"] and (below or _centred_below(L, figs[o], H))):
            figs[o].label_lines.append(L)
        else:
            free.append(L)
    return free


def _leader_runs(draw, L, hm=4.0) -> tuple[int, int]:
    """Length of the leader line leaving a label on its left and on its right side
    (a run of ink starting within a few px of the text edge, at the text's mid-height)."""
    H, W = draw.shape
    x0, y0, x1, y1 = L["box"]
    cy = (y0 + y1) // 2
    h = max(2, (y1 - y0) // 3)
    col = draw[max(0, cy - h):min(H, cy + h + 1), :].any(axis=0)

    def run(start, step):
        x, gap = start, 0
        while 0 <= x < W and not col[x] and gap < 1.3 * hm:  # leaders stop ~1 text-height short
            x += step
            gap += 1
        n, holes = 0, 0
        while 0 <= x < W and holes <= 1:
            if col[x]:
                n += 1
                holes = 0
            else:
                holes += 1
            x += step
        return n

    return run(x0 - 1, -1), run(x1, 1)


def _fig_under(box, figs, H):
    """Index of the figure directly above a text box (by x-centre), or None."""
    cx = (box[0] + box[2]) / 2
    best = None
    for i, f in enumerate(figs):
        fb = f.crop_box()
        gap = box[1] - fb[3]
        if fb[0] <= cx <= fb[2] and -0.04 * H <= gap <= 0.15 * H and (best is None or gap < best[0]):
            best = (gap, i)
    return best[1] if best else None


def _covers(box, figs, H):
    return [i for i, f in enumerate(figs)
            if box[0] <= f.cx <= box[2] and -0.04 * H <= box[1] - f.crop_box()[3] <= 0.15 * H]


def _rows(lines):
    """Cluster lines into visual rows (vertical overlap), top to bottom."""
    rows = []
    for L in sorted(lines, key=lambda l: (l["y0"] + l["y1"]) / 2):
        cy = (L["y0"] + L["y1"]) / 2
        if rows and cy <= rows[-1]["y1"]:
            rows[-1]["lines"].append(L)
            rows[-1]["y1"] = max(rows[-1]["y1"], L["y1"])
        else:
            rows.append(dict(lines=[L], y1=L["y1"]))
    return [sorted(r["lines"], key=lambda l: l["x0"]) for r in rows]


def _finish_block(B):
    rows = _rows(B["lines"])
    B["lines"] = [L for r in rows for L in r]
    B["text"] = clean_text(" ".join(l["text"] for l in B["lines"]))
    B["conf"] = float(np.mean([l["conf"] for l in B["lines"]]))
    B["weight"] = float(np.mean([l["weight"] for l in B["lines"]]))
    letters = [c for c in B["text"] if c.isalpha()]
    B["upper"] = bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.7
    B["rows"] = len(rows)
    return B


def _max_blank_run(page, A, B) -> int:
    """Longest run of ink-free columns between two same-row text blocks."""
    y0 = max(A["box"][1], B["box"][1])
    y1 = min(A["box"][3], B["box"][3])
    x0, x1 = A["box"][2], B["box"][0]
    if x1 <= x0 or y1 <= y0:
        return 0
    band = page["gray"][y0:y1, x0:x1] < page["ink_t"]
    col_ink = band.sum(axis=0) > 0
    run = best = 0
    for v in col_ink:
        run = 0 if v else run + 1
        best = max(best, run)
    return best


def caption_blocks(free_lines, page):
    """Re-join caption fragments: stacked lines (2-line captions) and same-row
    pieces that a leader line cut apart - but never two captions of two different figures."""
    H, W, figs = page["H"], page["W"], page["figs"]
    blocks = [_finish_block(dict(lines=[L], box=list(L["box"]))) for L in free_lines]
    merged = True
    while merged:
        merged = False
        blocks.sort(key=lambda B: (B["box"][1], B["box"][0]))
        for i in range(len(blocks)):
            for j in range(len(blocks)):
                if i == j:
                    continue
                A, B = blocks[i], blocks[j]
                ah, bh = A["box"][3] - A["box"][1], B["box"][3] - B["box"][1]
                aw, bw = A["box"][2] - A["box"][0], B["box"][2] - B["box"][0]
                lh = min(A["lines"][-1]["y1"] - A["lines"][-1]["y0"], B["lines"][0]["y1"] - B["lines"][0]["y0"])
                ok = False
                # stacked: B directly under A, overlapping in x, similar width
                vgap = B["box"][1] - A["box"][3]
                if (0 <= vgap <= 1.0 * lh and x_overlap(A["box"], B["box"]) > 0.3 * min(aw, bw)
                        and max(aw, bw) <= 1.8 * min(aw, bw)
                        and abs(A["weight"] - B["weight"]) < 0.12):
                    ok = True
                # same row: B right of A, and the space between them is not blank
                # (i.e. a word there was just missed by OCR / crossed by a leader line)
                vov = min(A["box"][3], B["box"][3]) - max(A["box"][1], B["box"][1])
                hgap = B["box"][0] - A["box"][2]
                if not ok and vov >= 0.5 * min(ah, bh) and -2 <= hgap <= 0.3 * W:
                    ok = _max_blank_run(page, A, B) <= 1.2 * lh
                if ok:
                    blocks[i] = _finish_block(dict(lines=A["lines"] + B["lines"], box=box_union(A["box"], B["box"])))
                    blocks.pop(j)
                    merged = True
                    break
            if merged:
                break
    return blocks


def figures_above(block, figs, H, max_gap):
    out = []
    for i, f in enumerate(figs):
        fb = f.crop_box()
        gap = block["box"][1] - fb[3]
        if -0.04 * H <= gap <= max_gap and x_overlap(fb, block["box"]) > 0:
            out.append((gap, i))
    return sorted(out)


def _gap_cut(f, cols, page):
    """Column where a box holds two separate drawings joined only by thin leader
    lines: a clear near-empty vertical gap with real drawing mass on both sides."""
    W, H = page["W"], page["H"]
    b = f.draw_box
    if b[2] - b[0] < 0.15 * W or len(cols) < 10:
        return None
    med = np.median(cols[cols > 0]) if (cols > 0).any() else 0
    low = cols <= 0.05 * med
    total = cols.sum()
    best = None
    i = 0
    while i < len(low):
        if low[i]:
            j = i
            while j < len(low) and low[j]:
                j += 1
            if j - i >= 0.02 * W:
                mid = (i + j) // 2
                left, right = cols[:i].sum(), cols[j:].sum()
                if left >= 0.15 * total and right >= 0.15 * total:
                    lm = f.pixel_mask[:, b[0]:b[0] + i]
                    rm = f.pixel_mask[:, b[0] + j:b[2]]
                    lh = np.ptp(np.where(lm.any(axis=1))[0]) if lm.any() else 0
                    rh = np.ptp(np.where(rm.any(axis=1))[0]) if rm.any() else 0
                    if lh >= 0.1 * H and rh >= 0.1 * H and (best is None or j - i > best[1]):
                        best = (b[0] + mid, j - i)
            i = j
        else:
            i += 1
    return best[0] if best else None


def split_merged_figures(page):
    """A drawing box with 2+ separate captions under it is really 2+ figures that
    were joined by a shared label's leader lines -> cut at the emptiest column."""
    figs, H = page["figs"], page["H"]
    free = attach_lines(page)
    blocks = caption_blocks(free, page)
    new_figs = []
    changed = False
    for f in figs:
        b = f.draw_box
        width = b[2] - b[0]
        under = [B for B in blocks
                 if 0 <= B["box"][1] - b[3] <= 0.12 * H
                 and b[0] <= (B["box"][0] + B["box"][2]) / 2 <= b[2]
                 and (B["box"][2] - B["box"][0]) < 0.6 * width]
        under.sort(key=lambda B: B["box"][0])
        disjoint = [B for i, B in enumerate(under) if i == 0 or B["box"][0] > under[i - 1]["box"][2]]
        cols = f.pixel_mask[:, b[0]:b[2]].sum(axis=0).astype(float)
        cols = np.convolve(cols, np.ones(5) / 5, mode="same")
        cuts = []
        if len(disjoint) < 2:
            cut = _gap_cut(f, cols, page)
            if cut is None:
                new_figs.append(f)
                continue
            cuts = [cut]
            disjoint = []
        for B1, B2 in zip(disjoint, disjoint[1:]):
            c1 = int((B1["box"][0] + B1["box"][2]) / 2) - b[0]
            c2 = int((B2["box"][0] + B2["box"][2]) / 2) - b[0]
            seg = cols[c1:c2]
            if len(seg) == 0:
                continue
            j = int(np.argmin(seg)) + c1
            if seg.min() <= 0.15 * np.median(cols[cols > 0]):
                cuts.append(j + b[0])
        if not cuts:
            new_figs.append(f)
            continue
        edges = [b[0]] + cuts + [b[2]]
        for xa, xb in zip(edges, edges[1:]):
            sub = np.zeros_like(f.pixel_mask)
            sub[:, xa:xb] = f.pixel_mask[:, xa:xb]
            ys, xs = np.where(sub)
            if len(xs) == 0:
                continue
            new_figs.append(Figure(draw_box=[int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                                   pixel_mask=sub))
        changed = True
    page["figs"] = new_figs
    return changed


def _ocr_crop(img, multi_line, scale):
    img = cv2.copyMakeBorder(img, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    up = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    d = pytesseract.image_to_data(up, config=f"--psm {6 if multi_line else 7}",
                                  output_type=pytesseract.Output.DICT)
    words = [(t.strip(), float(c)) for t, c in zip(d["text"], d["conf"]) if t and t.strip() and float(c) >= 0]
    words = [(t, c) for t, c in words if any(ch.isalnum() for ch in t)]
    if not words:
        return "", 0.0
    return clean_text(" ".join(t for t, _ in words)), float(np.mean([c for _, c in words]))


def reocr(page, box, multi_line=False) -> tuple[str, float]:
    """Read one text box again on its own - more accurate than the page-wide pass.
    Tries the original grey pixels (keeps thin strokes like 'I' and the dots in
    'T.S.') and the ink-only image; keeps the more confident reading."""
    H, W = page["H"], page["W"]
    x0, y0, x1, y1 = box
    hm = page["h_med"]
    if not multi_line and (y1 - y0) > 1.6 * hm:  # box swallowed a drawing line: keep the text band
        win = int(round(1.4 * hm))
        rows = (page["gray"][y0:y1, x0:x1] < page["ink_t"]).sum(axis=1)
        sums = np.convolve(rows, np.ones(win), mode="valid")
        top = y0 + int(np.argmax(sums))
        y0, y1 = top, top + win
    pad = 3
    b = clamp_box([x0 - pad, y0 - pad, x1 + pad, y1 + pad], W, H)
    cands = [_ocr_crop(page["gray"][b[1]:b[3], b[0]:b[2]], multi_line, 2),
             _ocr_crop(page["clean"][b[1]:b[3], b[0]:b[2]], multi_line, 3)]
    good = [tc for tc in cands if tc[1] >= 70]
    if len(good) > 1:  # both confident: keep the fuller reading (e.g. 'METAPHASE I' over 'METAPHASE')
        return max(good, key=lambda tc: (sum(ch.isalnum() for ch in tc[0]), tc[1]))
    return max(cands, key=lambda tc: tc[1])


def extend_caption_box(page, box):
    """Grow a caption box sideways over adjacent glyphs the sparse OCR pass missed
    (e.g. the 'T.S.' in 'T.S. OF ANTHER' or the 'II' in 'METAPHASE II')."""
    x0, y0, x1, y1 = box
    lh = max(6, y1 - y0)
    ink = page["gray"][y0:y1, :] < page["ink_t"]
    W = page["W"]
    limit = int(3 * lh)

    def walk(start, step):
        x, last_ink, blank = start, start, 0
        while 0 <= x + step < W and abs(x - start) < limit:
            x += step
            if ink[:, x].sum() >= 2:
                last_ink, blank = x, 0
            else:
                blank += 1
                if blank > 0.6 * lh:
                    break
        return last_ink

    return [walk(x0, -1), y0, walk(x1 - 1, 1) + 1, y1]


def best_text(page, block_text, block_conf, box, multi_line=False, extend=True):
    if extend and not multi_line:
        box = extend_caption_box(page, box)
    t2, c2 = reocr(page, box, multi_line)
    if not t2 or c2 < 60:
        return block_text, block_conf
    n1 = re.sub(r"[^a-z0-9]", "", block_text.lower())
    n2 = re.sub(r"[^a-z0-9]", "", t2.lower())
    if n1 and n1 in n2 and c2 >= 70:  # re-read is a superset (recovered a missed 'I', 'T.S.' ...)
        return t2, c2
    if c2 >= block_conf - 5 and len(t2) >= 0.6 * len(block_text):
        return t2, c2
    return block_text, block_conf


def assign_captions_and_groups(page):
    figs, H, W = page["figs"], page["H"], page["W"]
    free = attach_lines(page)
    for f in figs:
        f.caption_lines, f.group, f.caption_text, f.caption_conf = [], None, "", None
    blocks = caption_blocks(free, page)
    bold_t = page["bold_t"]
    groups, used = [], set()

    # 1) group titles: bold/UPPERCASE text spanning the centres of 2+ figures
    for B in blocks:
        cov = _covers(B["box"], figs, H)
        if len(cov) >= 2 and (B["upper"] or B["weight"] >= bold_t):
            t, c = best_text(page, B["text"], B["conf"], B["box"], B["rows"] > 1)
            groups.append(dict(title=t, box=B["box"], members=sorted(cov), conf=c))
            used.add(id(B))

    # 2) captions: for each figure, the BOLDEST free block centred under it
    proposals = {}
    for B in blocks:
        if id(B) in used:
            continue
        cand = figures_above(B, figs, H, max_gap=0.12 * H)
        if not cand:
            continue
        cov = [i for _g, i in cand if B["box"][0] <= figs[i].cx <= B["box"][2]]
        nearest = cand[0][1]
        if cov and cov != [nearest]:
            continue
        bcx = (B["box"][0] + B["box"][2]) / 2
        fb = figs[nearest].crop_box()
        if not (fb[0] <= bcx <= fb[2]):
            continue
        proposals.setdefault(nearest, []).append((B["weight"], -cand[0][0], B))
    for i, props in proposals.items():
        top_w = max(t[0] for t in props)
        props = [t for t in props if t[0] >= top_w - 0.06]  # the boldest ones...
        props.sort(key=lambda t: t[1], reverse=True)          # ...and of those the nearest
        w, _g, B = props[0]
        # a non-bold block only becomes a caption if nothing bolder exists and it isn't a lone label word
        if w < bold_t and len(props) > 1:
            continue
        figs[i].caption_lines = list(B["lines"])
        figs[i].caption_text, figs[i].caption_conf = best_text(page, B["text"], B["conf"], B["box"], B["rows"] > 1)
        used.add(id(B))

    # 3) page-level title: UPPERCASE bold block below 2+ figures that isn't anyone's caption
    for B in blocks:
        if id(B) in used or not B["upper"] or len(B["text"]) < 6 or B["weight"] < 0.09:
            continue
        above = [i for i, f in enumerate(figs) if f.crop_box()[3] <= B["box"][1] + 0.02 * H]
        nearest_gap = min((B["box"][1] - figs[i].crop_box()[3] for i in above), default=1e9)
        if len(above) >= 2 and nearest_gap <= 0.15 * H:
            members = [i for i in above if all(i not in g["members"] for g in groups)]
            if len(members) >= 2:
                t, c = best_text(page, B["text"], B["conf"], B["box"])
                groups.append(dict(title=t, box=B["box"], members=members, conf=c))
                used.add(id(B))

    # 4) leftover free text next to a figure = its label (leader line didn't quite touch).
    #    The side its leader line leaves from tells which neighbouring figure it belongs to.
    near = int(W * 0.05)
    draw = page["leader_ink"]
    hm = page["h_med"]
    pending = []
    for B in blocks:
        if id(B) in used:
            continue
        for L in B["lines"]:
            if L["bold"] and page["bold_t"] < 0.2:
                continue                  # bold body text near a figure (e.g. 'Type - ...') is not a label
            pending.append(L)
    pending.sort(key=lambda l: (l["y0"], l["x0"]))
    for L in pending:
        x0, y0, x1, y1 = L["box"]
        lcx = (x0 + x1) / 2
        left, right = _leader_runs(draw, L, hm)
        # 2nd line of a 2-line label: aligned under a label line and no leader of its own
        # on the side facing that label's figure -> same figure
        above = [(i, M) for i, f in enumerate(figs) for M in f.label_lines
                 if 0 <= y0 - M["y1"] <= 0.9 * hm and abs(x0 - M["x0"]) <= 2.5 * hm]
        if above:
            i = above[0][0]
            facing = left if figs[i].cx < lcx else right
            if facing < 5:
                figs[i].label_lines.append(L)
                continue
        d = [(_dist_box(L["box"], f.draw_box), i) for i, f in enumerate(figs)]
        d = [t for t in d if t[0] <= near]
        side = []
        if max(left, right) >= 5 and left != right:
            side = [t for t in d if (figs[t[1]].cx < lcx) == (left > right)]
        pick = min(side or d, default=None)
        if pick is not None:
            figs[pick[1]].label_lines.append(L)

    # keep only real labels (leader line / continuation line) and join 2-line labels
    for f in figs:
        f.label_lines, f.label_texts = clean_labels(page, f)

    # crops: don't stretch a figure's crop over a NEIGHBOUR's drawing just to include a shared label
    for i, f in enumerate(figs):
        others = [g.draw_box for j, g in enumerate(figs) if j != i]
        f.crop_labels = [L for L in f.label_lines
                         if not any(x_overlap(L["box"], o) > 0 and min(L["y1"], o[3]) - max(L["y0"], o[1]) > 0
                                    for o in others)]

    for gi, g in enumerate(groups):
        for i in g["members"]:
            figs[i].group = gi
    return groups


def _has_leader(draw, L, fig, hm) -> bool:
    """Does a leader line arrive at this text line? Checked on the side facing its
    figure (horizontal line) and directly above / below the text (vertical line)."""
    H, W = draw.shape
    x0, y0, x1, y1 = L["box"]
    cy = (y0 + y1) // 2
    h = max(2, (y1 - y0) // 3)

    def hrun(start, step):
        col = draw[max(0, cy - h):min(H, cy + h + 1), :].any(axis=0)
        x, gap = start, 0
        while 0 <= x < W and not col[x] and gap < 1.3 * hm:  # leaders stop ~1 text-height short
            x += step
            gap += 1
        n = 0
        while 0 <= x < W and col[x]:
            n += 1
            x += step
        return n

    def vrun(start, step):
        xa, xb = x0 + 2, max(x0 + 3, x1 - 2)
        row = draw[:, xa:xb].any(axis=1)
        y, gap = start, 0
        while 0 <= y < H and not row[y] and gap < 0.8 * hm:
            y += step
            gap += 1
        n = 0
        while 0 <= y < H and row[y]:
            n += 1
            y += step
        return n

    facing_left = fig.cx < (x0 + x1) / 2
    horiz = hrun(x0 - 1, -1) if facing_left else hrun(x1, 1)
    return horiz >= 3 or vrun(y0 - 1, -1) >= 4 or vrun(y1, 1) >= 4


def clean_labels(page, f):
    """A label printed in the manual always has a leader line or continues the label
    line right above it. OCR fragments of drawing texture / show-through / body text
    have neither -> dropped. Returns (kept lines, label strings, 2-line labels joined)."""
    draw = page["leader_ink"]
    b = f.draw_box
    bw, bh = b[2] - b[0], b[3] - b[1]
    inner = [b[0] + 0.08 * bw, b[1] + 0.08 * bh, b[2] - 0.08 * bw, b[3] - 0.08 * bh]
    hm = page["h_med"]
    lines = sorted(f.label_lines, key=lambda l: (l["y0"], l["x0"]))
    kept, texts = [], []
    for L in lines:
        t, c = best_text(page, clean_text(L["text"]), L["conf"], L["box"], extend=False)
        t = clean_text(t)
        letters = sum(ch.isalpha() for ch in t)
        if letters < 2:
            continue
        lx, ly = (L["x0"] + L["x1"]) / 2, (L["y0"] + L["y1"]) / 2
        inside = inner[0] <= lx <= inner[2] and inner[1] <= ly <= inner[3]
        if inside and len(t.split()) == 1 and (c < 90 or letters < 4):
            continue                      # texture inside the drawing read as a 'word'
        leader = _has_leader(draw, L, f, hm)
        if L["y1"] <= b[1] + 0.02 * bh and not leader:
            continue                      # text above the drawing without a leader = body text, not a label
        prev = kept[-1] if kept else None
        cont = (prev is not None and 0 <= L["y0"] - prev["y1"] <= 0.9 * hm
                and abs(L["x0"] - prev["x0"]) <= 2.5 * hm)
        single = len(t.split()) == 1
        if not leader and not cont and single and (c < 85 or letters < 4):
            continue                      # lone weak word with no leader line = OCR noise
        if cont and not leader:
            texts[-1] = f"{texts[-1]} {t}"  # 2nd line of a 2-line label
        else:
            texts.append(t)
        kept.append(L)
    out = []
    for t in texts:
        if t not in out:
            out.append(t)
    return kept, out


def reading_order(figs):
    """Sort figures row by row, left to right."""
    figs = sorted(figs, key=lambda f: f.draw_box[1])
    rows = []
    for f in figs:
        cy = (f.draw_box[1] + f.draw_box[3]) / 2
        for r in rows:
            if r["y0"] <= cy <= r["y1"]:
                r["f"].append(f)
                break
        else:
            rows.append(dict(y0=f.draw_box[1], y1=f.draw_box[3], f=[f]))
    out = []
    for r in rows:
        out.extend(sorted(r["f"], key=lambda f: f.draw_box[0]))
    return out


# =============================================================================
# manual text (exercise title + explanation paragraphs) from the source PDF
# =============================================================================
class ManualText:
    """Reads the manual's own text pages (OCR) to find (1) which exercise a page
    belongs to and (2) the paragraph that explains a figure. Nothing is generated:
    every string returned is OCR text copied from the manual, or '' if not found."""

    ENUM = re.compile(r"^\s*[\(\{\[]?([A-H]|[a-h]|\d{1,2}|i{1,3}|iv|v)[\)\}\]\.]\s+")

    def __init__(self, pdf_path: Path | None, ink_t: int):
        self.doc = None
        self.ink_t = ink_t
        self.cache: dict[int, list[str]] = {}
        self.headings: dict[int, tuple[int, str]] | None = None
        if pdf_path and pdf_path.exists():
            import pymupdf
            self.doc = pymupdf.open(pdf_path)

    # ---------------------------------------------------------------- pages
    def page_lines(self, pdf_page: int) -> list[str]:
        if pdf_page in self.cache:
            return self.cache[pdf_page]
        bgr = pdf_page_to_bgr(self.doc, pdf_page)
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        clean = np.where(g < self.ink_t, g, 255).astype(np.uint8)
        up = cv2.resize(clean, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        d = pytesseract.image_to_data(up, config="--psm 3", output_type=pytesseract.Output.DICT)
        rows: dict[tuple, list] = {}
        order = []
        for i, w in enumerate(d["text"]):
            if w and w.strip() and float(d["conf"][i]) >= 0:
                key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
                if key not in rows:
                    rows[key] = []
                    order.append(key)
                rows[key].append((w.strip(), float(d["conf"][i])))
        lines = []
        for key in order:
            ws = rows[key]
            if np.mean([c for _, c in ws]) < 45:
                continue  # unreadable scrap (show-through, stains)
            t = clean_text(" ".join(w for w, _ in ws))
            if t:
                lines.append(t)
        self.cache[pdf_page] = lines
        return lines

    # ---------------------------------------------------------------- exercise titles
    def _banner(self, pdf_page: int):
        """Exercise banners are dark text on a grey box: threshold hard, then OCR."""
        g = cv2.cvtColor(pdf_page_to_bgr(self.doc, pdf_page), cv2.COLOR_BGR2GRAY)
        top = g[: int(g.shape[0] * 0.2), :]
        best = None
        for t in (70, 100):
            b = np.where(top < t, 0, 255).astype(np.uint8)
            up = cv2.resize(b, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            d = pytesseract.image_to_data(up, config="--psm 6", output_type=pytesseract.Output.DICT)
            rows: dict[tuple, list] = {}
            for i, w in enumerate(d["text"]):
                if w and w.strip() and float(d["conf"][i]) >= 0:
                    rows.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(
                        (w.strip(), float(d["conf"][i])))
            for ws in rows.values():
                line = " ".join(w for w, _ in ws)
                m = re.search(r"EXER\S*\s*[-–—:.«¢+]*\s*\.?(\d{1,2})\s*[-–—:;.]+\s*(.+)", line, re.I)
                if m:
                    conf = float(np.mean([c for _, c in ws]))
                    title = re.sub(r"[^A-Za-z0-9 ,&()'\-]+", "", m.group(2)).strip(" -|")
                    if best is None or conf > best[2]:
                        best = (int(m.group(1)), title, conf)
        return best

    def _build_headings(self, last_page: int):
        found = []
        for p in range(1, min(len(self.doc), last_page) + 1):
            r = self._banner(p)
            if r:
                found.append([p, r[0], r[1]])
        # exercise numbers run 1,2,3... - repair single OCR digit slips (e.g. 3 read as 8)
        for i in range(len(found)):
            prev_n = found[i - 1][1] if i > 0 else 0
            next_n = found[i + 1][1] if i + 1 < len(found) else None
            if found[i][1] != prev_n + 1 and (next_n == prev_n + 2 or (next_n is None and i > 0)):
                found[i][1] = prev_n + 1
        self.headings = {p: (n, t) for p, n, t in found}

    def exercise_title(self, pdf_page: int, last_page: int) -> tuple[str, int | None]:
        if self.doc is None:
            return "", None
        if self.headings is None:
            self._build_headings(last_page)
        starts = [p for p in self.headings if p <= pdf_page]
        if not starts:
            return "", None
        p = max(starts)
        n, t = self.headings[p]
        return f"Exercise {n}: {t.title()}", p

    def next_exercise_page(self, pdf_page: int) -> int | None:
        later = [p for p in (self.headings or {}) if p > pdf_page]
        return min(later) if later else None

    # ---------------------------------------------------------------- explanations
    @staticmethod
    def _norm(s: str) -> str:
        s = s.lower()
        s = re.sub(r"^[\s•\-–*>»+]*([\(\{\[]?[a-h0-9ivx]{1,4}[\)\}\]\.:]\s+)?", "", s)
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def _numeral(s: str) -> str:
        m = re.search(r"\b(i{1,3}|iv)\s*$", s)
        return m.group(1) if m else ""

    def _level(self, line: str):
        m = self.ENUM.match(line)
        if not m:
            return None
        tok = m.group(1)
        if tok.isupper():
            return 1
        if re.fullmatch(r"i{1,3}|iv|v", tok):
            return 3
        return 2

    def explanation(self, caption: str, pdf_page: int, ex_start: int | None,
                    stop_captions: list[str], labels: list[str] | None = None,
                    page_offset: int = 1) -> tuple[str, int | None]:
        """Paragraph whose heading matches the caption (exact OCR text), or ''."""
        if self.doc is None or not caption or len(caption) < 4:
            return "", None
        cap = self._norm(caption)
        cap_num = self._numeral(cap)
        cap_words = len(cap.split())
        others = [self._norm(c) for c in stop_captions if c and self._norm(c) != cap and len(self._norm(c)) >= 4]
        lo = ex_start or max(1, pdf_page - 3)
        hi = pdf_page + 1
        nxt = self.next_exercise_page(pdf_page)
        if nxt is not None:
            hi = min(hi, nxt - 1)
        best = (0.0, None, None)
        for p in range(lo, min(hi, len(self.doc)) + 1):
            lines = self.page_lines(p)
            for i, line in enumerate(lines):
                head_raw = re.split(r"\s[:\-–]\s|:", line, maxsplit=1)[0]
                head = self._norm(head_raw)
                if not head:
                    continue
                nline = self._norm(line)
                if p == pdf_page and (len(nline.split()) <= cap_words + 1 or any(
                        st and st in nline for st in others)):
                    continue      # on the figure's own page skip caption rows / label lines
                h_num = self._numeral(head) or self._numeral(nline[:len(cap) + 2].strip())
                if h_num and h_num != cap_num:
                    continue      # 'Anaphase I' must never match 'Anaphase II'
                cand = nline[:len(cap)]
                score = max(difflib.SequenceMatcher(None, cap, head).ratio(),
                            difflib.SequenceMatcher(None, cap, cand).ratio())
                if cap_num and not h_num:  # OCR often drops a trailing 'I' -> allow, slightly penalised
                    score = max(score, difflib.SequenceMatcher(None, cap[:-len(cap_num)].strip(), head).ratio()) - 0.03
                if self._level(line) is not None or line.rstrip().endswith(":") or ":" in line[:len(caption) + 6]:
                    score += 0.05  # looks like a heading
                if score > best[0]:
                    best = (score, p, i)
        score, p, i = best
        if score < 0.82 or p is None:
            return "", None
        lines = self.page_lines(p)
        para = [lines[i]]
        enumerated = self._level(lines[i]) is not None
        lvl = self._level(lines[i]) or 1
        stops = [self._norm(c) for c in stop_captions if c and self._norm(c) != cap]
        own = [self._norm(x) for x in (labels or []) + [caption] if x and len(self._norm(x)) >= 3]
        printed_no = str(p - page_offset)
        for nxt_line in lines[i + 1:i + 16]:
            nl = self._level(nxt_line)
            if nl is not None and nl <= lvl:
                break         # next item at the same level, e.g. '(b) Metaphase' after '(a) Prophase'
            words = nxt_line.split()
            letters = sum(ch.isalpha() for ch in nxt_line)
            if letters < 0.5 * len(nxt_line.replace(" ", "")) or (
                    len(words) <= 5 and printed_no in re.findall(r"\d+", nxt_line)):
                break         # page number / scan noise at the bottom of the page
            if len(words) <= 4 and any(
                    difflib.SequenceMatcher(None, o, self._norm(nxt_line)).ratio() >= 0.8 for o in own):
                break         # reached this figure's own labels / caption (figure page)
            if enumerated and re.match(r"^[A-Z][A-Za-z .]{2,30}\s?:", nxt_line):
                break         # e.g. 'Placentation : ...' starts a new topic after '(e) Pentalocular'
            n = self._norm(nxt_line)
            if re.match(r"exercise\b", n) or any(
                    st and difflib.SequenceMatcher(None, st, n[:len(st)]).ratio() >= 0.88 for st in stops):
                break         # next figure's heading
            para.append(nxt_line)
        return clean_text(" ".join(para)), p


# =============================================================================
# main
# =============================================================================
def word_blobs(page):
    """Printed words as ink blobs (letters joined horizontally) - used so a crop never cuts a word in half."""
    if "word_blobs" in page:
        return page["word_blobs"]
    h = max(6, int(page["h_med"]))
    ink = ((page["gray"] < page["ink_t"]) * 255).astype(np.uint8)
    fx0, fy0, fx1, fy1 = page["frame"]
    mask = np.zeros_like(ink)
    mask[fy0:fy1, fx0:fx1] = ink[fy0:fy1, fx0:fx1]
    joined = cv2.dilate(mask, np.ones((max(3, h // 3), max(3, int(h * 0.6))), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(joined, 8)
    blobs = []
    for i in range(1, n):
        x, y, w, hh, area = st[i]
        # word-sized only: not a whole drawing, not a long thin leader line
        if hh <= 2.2 * h and w <= 0.35 * page["W"] and hh >= 0.5 * h:
            blobs.append([int(x), int(y), int(x + w), int(y + hh)])
    # plus every word OCR read on the page (catches a label whose ink touches its pointer line)
    for L in page["text_lines"]:
        for w in L["words"]:
            blobs.append([int(w["x0"]), int(w["y0"]), int(w["x1"]), int(w["y1"])])
    page["word_blobs"] = blobs
    return blobs


def whole_words(page, box):
    """Grow a crop box until no printed word (label) is cut by its edge."""
    b = list(box)
    for _ in range(6):
        grown = False
        for w in word_blobs(page):
            inside = w[0] < b[2] and w[2] > b[0] and w[1] < b[3] and w[3] > b[1]
            whole = w[0] >= b[0] and w[2] <= b[2] and w[1] >= b[1] and w[3] <= b[3]
            if inside and not whole:
                b = [min(b[0], w[0]), min(b[1], w[1]), max(b[2], w[2]), max(b[3], w[3])]
                grown = True
        if not grown:
            break
    return b


def save_crop(bgr, box, pad, path: Path):
    H, W = bgr.shape[:2]
    b = clamp_box([box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad], W, H)
    crop = bgr[b[1]:b[3], b[0]:b[2]]
    cv2.imwrite(str(path), crop, [cv2.IMWRITE_PNG_COMPRESSION, 6])  # PNG = lossless
    return b, crop.shape[1], crop.shape[0]


def build_description(caption, group_title, exercise, labels, manual):
    parts = []
    head = caption or "(no printed caption)"
    if group_title:
        head += f" - part of '{group_title}'"
    if exercise:
        head += f" [{exercise}]"
    parts.append(head + ".")
    if labels:
        parts.append("Labelled parts: " + "; ".join(labels) + ".")
    if manual:
        parts.append("Manual text: " + manual)
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(PAGES_MANIFEST), help="pages_manifest.csv from extract_pages.py")
    ap.add_argument("--out-images", default=str(IMAGES_DIR))
    ap.add_argument("--csv", default=str(IMAGES_CSV))
    ap.add_argument("--overlays", default=str(DATA_DIR / "review_overlays"))
    ap.add_argument("--ink-threshold", type=int, default=120,
                    help="gray level below which a pixel counts as printed ink (removes show-through)")
    ap.add_argument("--pad", type=int, default=6, help="white margin (px) kept around each crop")
    ap.add_argument("--no-manual-text", action="store_true", help="skip looking up explanations in the manual")
    ap.add_argument("--no-groups", action="store_true", help="save individual figures only")
    args = ap.parse_args()

    if not configure_tesseract():
        print("ERROR: Tesseract OCR was not found. Install it (see README.md) or set the "
              "TESSERACT_CMD environment variable to the full path of tesseract(.exe).", file=sys.stderr)
        return 1

    manifest = resolve_cli_path(args.manifest)
    if not manifest.exists():
        print(f"ERROR: {manifest} not found - run extract_pages.py first", file=sys.stderr)
        return 1
    with open(manifest, newline="", encoding="utf-8-sig") as f:
        pages = list(csv.DictReader(f))
    if not pages:
        print("ERROR: manifest is empty", file=sys.stderr)
        return 1

    out_dir = resolve_cli_path(args.out_images)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in list(out_dir.glob("img_*.png")) + list(out_dir.glob("grp_*.png")):
        old.unlink()
    ov_dir = resolve_cli_path(args.overlays)
    ov_dir.mkdir(parents=True, exist_ok=True)
    for old in ov_dir.glob("page_*.jpg"):
        old.unlink()

    src_pdf = None
    if not args.no_manual_text:
        src_pdf = resolve_link(pages[0]["source_pdf_link"]) if pages[0].get("source_pdf_link") else None
        if src_pdf is not None and not src_pdf.exists():
            print(f"[warn] source PDF {src_pdf} not found - manual text will be empty")
    manual = ManualText(src_pdf, args.ink_threshold)

    rows = []
    last_pdf_page = max(int(pg["pdf_page"]) for pg in pages)
    for pg in pages:
        pdf_page, printed = int(pg["pdf_page"]), int(pg["printed_page"])
        page_path = resolve_link(pg["page_image_link"])
        bgr = cv2.imread(str(page_path), cv2.IMREAD_COLOR)
        if bgr is None:
            print(f"[warn] cannot read {page_path}, skipped")
            continue
        page = analyse_page(bgr, args.ink_threshold)
        attach_lines(page)
        split_merged_figures(page)
        page["figs"] = reading_order(page["figs"])
        groups = assign_captions_and_groups(page)
        figs = page["figs"]
        W, H = page["W"], page["H"]

        exercise, ex_start = (manual.exercise_title(pdf_page, last_pdf_page + 1)
                              if not args.no_manual_text else ("", None))

        # no printed group title, but 3+ figures from one exercise -> group them under the exercise
        if not args.no_groups and not groups and len(figs) >= 3:
            groups.append(dict(title=exercise or f"Figures on page {printed}", box=None,
                               members=list(range(len(figs))), conf=None, from_exercise=True))
            for i in range(len(figs)):
                figs[i].group = 0
        if args.no_groups:
            groups = []
            for f in figs:
                f.group = None

        vis = bgr.copy()
        group_ids = {}
        for gi, g in enumerate(groups):
            group_ids[gi] = f"grp_{pdf_page:03d}_{gi + 1}"

        for n, f in enumerate(figs, start=1):
            img_id = f"img_{pdf_page:03d}_{n:02d}"
            path = out_dir / f"{img_id}.png"
            box, cw, ch = save_crop(bgr, whole_words(page, f.crop_box()), args.pad, path)
            caption = f.caption()
            labels = f.label_texts
            g = groups[f.group] if f.group is not None else None
            gtitle = g["title"] if g else ""
            mtext, mpage = "", None  # filled in a second pass (needs every caption as a stop marker)
            conf = f.caption_conf
            review = []
            if not caption:
                review.append("no_caption")
            elif conf is not None and conf < 75:
                review.append("low_ocr_conf")
            rows.append(dict(
                image_id=img_id, image_type="figure", group_id=group_ids.get(f.group, ""),
                image_link=to_link(path), page_image_link=pg["page_image_link"],
                pdf_page=pdf_page, printed_page=printed, exercise_title=exercise,
                caption=caption, group_title=gtitle, labels="; ".join(labels),
                manual_text=mtext, manual_text_printed_page=(mpage - (pdf_page - printed)) if mpage else "",
                description=build_description(caption, gtitle, exercise, labels, mtext),
                bbox_x0=box[0], bbox_y0=box[1], bbox_x1=box[2], bbox_y1=box[3],
                bbox_norm_x0=round(box[0] / W, 5), bbox_norm_y0=round(box[1] / H, 5),
                bbox_norm_x1=round(box[2] / W, 5), bbox_norm_y1=round(box[3] / H, 5),
                drawing_bbox_x0=f.draw_box[0], drawing_bbox_y0=f.draw_box[1],
                drawing_bbox_x1=f.draw_box[2], drawing_bbox_y1=f.draw_box[3],
                page_width_px=W, page_height_px=H, crop_width_px=cw, crop_height_px=ch,
                caption_ocr_conf=round(conf, 1) if conf is not None else "",
                needs_review=";".join(review), image_sha256=sha256_of(path),
                _ex_start=ex_start, _labels=labels,
            ))
            cv2.rectangle(vis, tuple(box[:2]), tuple(box[2:]), (0, 0, 255), 2)
            cv2.putText(vis, f"{n}", (box[0] + 4, box[1] + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            for L in f.caption_lines:
                cv2.rectangle(vis, tuple(L["box"][:2]), tuple(L["box"][2:]), (0, 150, 0), 2)

        for gi, g in enumerate(groups):
            members = [figs[i] for i in g["members"]]
            gbox = members[0].crop_box()
            for m in members[1:]:
                gbox = box_union(gbox, m.crop_box())
            for m in members:
                for L in m.caption_lines:
                    gbox = box_union(gbox, L["box"])
            if g.get("box"):
                gbox = box_union(gbox, g["box"])
            gid = group_ids[gi]
            path = out_dir / f"{gid}.png"
            box, cw, ch = save_crop(bgr, gbox, args.pad, path)
            member_caps = [m.caption() or "(uncaptioned)" for m in members]
            desc = f"{g['title']}" + (f" [{exercise}]" if exercise and exercise != g["title"] else "")
            desc += ". Contains: " + "; ".join(member_caps) + "."
            rows.append(dict(
                image_id=gid, image_type="group", group_id=gid, image_link=to_link(path),
                page_image_link=pg["page_image_link"], pdf_page=pdf_page, printed_page=printed,
                exercise_title=exercise, caption="", group_title=g["title"],
                labels="", manual_text="", manual_text_printed_page="", description=desc,
                bbox_x0=box[0], bbox_y0=box[1], bbox_x1=box[2], bbox_y1=box[3],
                bbox_norm_x0=round(box[0] / W, 5), bbox_norm_y0=round(box[1] / H, 5),
                bbox_norm_x1=round(box[2] / W, 5), bbox_norm_y1=round(box[3] / H, 5),
                drawing_bbox_x0="", drawing_bbox_y0="", drawing_bbox_x1="", drawing_bbox_y1="",
                page_width_px=W, page_height_px=H, crop_width_px=cw, crop_height_px=ch,
                caption_ocr_conf=round(g["conf"], 1) if g.get("conf") else "",
                needs_review="group_title_from_exercise" if g.get("from_exercise") else "",
                image_sha256=sha256_of(path), _ex_start=None, _labels=[],
            ))
            cv2.rectangle(vis, tuple(box[:2]), tuple(box[2:]), (255, 120, 0), 1)
            if g.get("box"):
                cv2.rectangle(vis, tuple(g["box"][:2]), tuple(g["box"][2:]), (255, 120, 0), 2)

        cv2.imwrite(str(ov_dir / f"page_{pdf_page:03d}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 90])
        caps = [f.caption() or "?" for f in figs]
        print(f"  printed p{printed:>3} (pdf {pdf_page:>3}): {len(figs)} figure(s), {len(groups)} group(s) -> {caps}")

    # second pass: the manual's own explanation for each figure
    if not args.no_manual_text and manual.doc is not None:
        all_caps = [r["caption"] for r in rows if r["image_type"] == "figure" and r["caption"]]
        all_caps += [r["group_title"] for r in rows if r["image_type"] == "group" and r["group_title"]]
        print("[info] looking up each figure's explanation in the manual text ...")
        for r in rows:
            if r["image_type"] != "figure":
                continue
            off = r["pdf_page"] - r["printed_page"]
            mtext, mpage = manual.explanation(r["caption"], r["pdf_page"], r.get("_ex_start"), all_caps,
                                              labels=r["_labels"], page_offset=off)
            r["manual_text"] = mtext
            r["manual_text_printed_page"] = (mpage - off) if mpage else ""
            r["description"] = build_description(r["caption"], r["group_title"], r["exercise_title"],
                                                 r["_labels"], mtext)
    for r in rows:
        r.pop("_ex_start", None)
        r.pop("_labels", None)

    csv_path = resolve_cli_path(args.csv)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:  # -sig: opens cleanly in Excel
        wr = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        wr.writeheader()
        wr.writerows(rows)
    n_fig = sum(r["image_type"] == "figure" for r in rows)
    n_grp = len(rows) - n_fig
    print(f"[done] {n_fig} figure image(s) + {n_grp} group image(s) -> {to_link(out_dir)}/")
    print(f"       CSV: {to_link(csv_path)}   overlays for checking: {to_link(ov_dir)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
