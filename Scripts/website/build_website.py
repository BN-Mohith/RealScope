"""
Build the RealScope website from the current specimen list.

Reads   Data/selected_specimens.json                  your CSV, matched to diagrams (catalog.py)
        Data/real_slide_images/photos_manifest.csv    supplied images (fetch_real_images.py)
        Data/raw_data/images_metadata.csv             diagram pages / exercises (extraction)
        Data/website/img/diagrams/, manual/, img/mistakes/   (prepare_display_images.py, make_mistake_images.py)
        Scripts/website/site_content.py               labels, descriptions, topics, mistakes text
Writes  Data/website/index.html, style.css, app.js, site_data.js
        Data/website/img/photos/<image_id>.<ext> (+ thumbs/)   copies of the supplied images
        Data/website_report.csv                       one row per specimen: diagram / image / page link status

Open Data/website/index.html in any browser - no server or internet needed (only the fonts use the internet).

    python Scripts/website/build_website.py
"""
from __future__ import annotations

import csv
import json
import urllib.parse
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "website"))
from site_assets import APP_JS, INDEX_HTML, STYLE_CSS  # noqa: E402
from site_content import EXERCISES, MISTAKES, SPECIMENS, TOPICS  # noqa: E402

CSV_PATH = REPO / "Data" / "raw_data" / "images_metadata.csv"
SELECTED = REPO / "Data" / "selected_specimens.json"
MANIFEST = REPO / "Data" / "real_slide_images" / "photos_manifest.csv"
REPORT = REPO / "Data" / "website_report.csv"
SITE = REPO / "Data" / "website"
DIAG = SITE / "img" / "diagrams"
PHOTOS = SITE / "img" / "photos"
THUMBS = PHOTOS / "thumbs"
MIST = SITE / "img" / "mistakes"
MANUAL = SITE / "manual"


def rel(p: Path) -> str:
    return p.relative_to(SITE).as_posix()


def exercise_number(title: str) -> int | None:
    m = re.search(r"Exercise\s+(\d+)", title or "", re.I)
    return int(m.group(1)) if m else None


def online_photo(link: str, pr: dict):
    """No downloaded copy yet -> the website loads the image straight from its supplied link
    (works in any normal browser; a downloaded copy is used instead once run_all.py has fetched it)."""
    if pr.get("status") == "held_back" or not link or not link.strip().lower().startswith(("http://", "https://", "//", "www.")):
        return None
    url = link.strip()
    if url.startswith("//"):
        url = "https:" + url
    if url.lower().startswith("www."):
        url = "https://" + url
    parts = urllib.parse.urlsplit(url)
    if "utm_" in parts.query:
        q = "&".join(kv for kv in parts.query.split("&") if not kv.lower().startswith("utm_"))
        url = urllib.parse.urlunsplit(parts._replace(query=q))
    url = url.replace("://thumb.wikimedia.org/", "://upload.wikimedia.org/")
    return {"src": url, "thumb": url, "remote": True}


def copy_photos(rows: list[dict]) -> dict[str, dict]:
    """Copy each available supplied image into the site (+ a small thumbnail for the gallery).
    Unchanged files are left alone; files of removed specimens are deleted."""
    import cv2
    PHOTOS.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)
    out, keep = {}, set()
    for r in rows:
        if r["status"] != "ok" or not r["file"]:
            continue
        src = REPO / r["file"]
        if not src.exists():
            continue
        dest = PHOTOS / f"{r['image_id']}{src.suffix.lower()}"
        thumb = THUMBS / f"{r['image_id']}.jpg"
        if not dest.exists() or dest.stat().st_size != src.stat().st_size or dest.read_bytes() != src.read_bytes():
            shutil.copy2(src, dest)
            thumb.unlink(missing_ok=True)
        if not thumb.exists():
            im = cv2.imread(str(dest), cv2.IMREAD_COLOR)
            if im is not None:
                h, w = im.shape[:2]
                s = min(1.0, 360 / max(h, w))
                cv2.imwrite(str(thumb), cv2.resize(im, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA),
                            [cv2.IMWRITE_JPEG_QUALITY, 82])
        keep.update({dest.name, thumb.name})
        out[r["image_id"]] = {"src": rel(dest), "thumb": rel(thumb) if thumb.exists() else rel(dest),
                              "w": int(r["width_px"] or 0), "h": int(r["height_px"] or 0)}
    for d in (PHOTOS, THUMBS):
        for p in d.iterdir():
            if p.is_file() and p.name not in keep:
                p.unlink()
    return out


def page_offset(meta_rows: list[dict]) -> int | None:
    """printed page = PDF page - offset, if every extracted page agrees (checked, not assumed)."""
    offs = {int(r["pdf_page"]) - int(r["printed_page"]) for r in meta_rows if r.get("printed_page")}
    return offs.pop() if len(offs) == 1 else None


def main() -> int:
    for p, step in ((CSV_PATH, "the extraction"), (SELECTED, "catalog.py"), (DIAG, "prepare_display_images.py")):
        if not p.exists():
            sys.exit(f"[X] {p.relative_to(REPO).as_posix()} not found - run {step} first (Scripts/run_all.py does all steps).")
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        meta = {r["image_id"]: r for r in csv.DictReader(f) if r["image_type"] == "figure"}
    selected = json.loads(SELECTED.read_text(encoding="utf-8"))["specimens"]
    photo_rows = []
    if MANIFEST.exists():
        with open(MANIFEST, encoding="utf-8-sig", newline="") as f:
            photo_rows = list(csv.DictReader(f))
    pinfo = {r["image_id"]: r for r in photo_rows}
    photos = copy_photos(photo_rows)

    specimens, report = [], []
    for sel in selected:
        iid = sel["image_id"]
        m = meta[iid]
        c = SPECIMENS.get(iid, {})
        img, plain = DIAG / f"{iid}.png", DIAG / f"{iid}_nolabels.png"
        labels = c.get("labels", [])
        exn = exercise_number(m["exercise_title"]) or 0
        pr = pinfo.get(iid, {})
        specimens.append({
            "id": iid, "caption": sel["figure"], "cat": c.get("cat") if c.get("cat") in TOPICS else next(iter(TOPICS)),
            "labels": labels, "desc": c.get("desc", ""),
            "exn": exn, "ex": EXERCISES.get(exn, re.sub(r"^Exercise\s+\d+:\s*", "", m["exercise_title"] or "")),
            "pdf": int(m["pdf_page"]), "page": int(m["printed_page"]),
            "img": rel(img), "imgPlain": rel(plain) if plain.exists() and labels else None,
            "link": sel["link"], "licence": sel["licence"], "magnification": sel["magnification"],
            "photo": photos.get(iid) or online_photo(sel["link"], pr),
            "photoInfo": {"status": pr.get("status", "not_downloaded"), "note": pr.get("note", ""),
                          "resolved": pr.get("resolved_url", "")},
        })
        report.append({"csv_no": sel["csv_no"], "figure": sel["figure"], "image_id": iid, "printed_page": m["printed_page"],
                       "pdf_page": m["pdf_page"], "diagram": "ok" if img.exists() else "MISSING",
                       "supplied_image": "ok" if iid in photos else ("loaded from its link" if online_photo(sel["link"], pr) else pr.get("status", "not_downloaded")),
                       "image_note": pr.get("note", ""), "link": sel["link"]})

    used = []
    for s in specimens:
        if s["cat"] not in used:
            used.append(s["cat"])
    topics = {k: v for k, v in TOPICS.items() if k in used}

    mistakes = []
    for mk in MISTAKES:
        real = MIST / "real" / f"{mk['image']}.jpg"
        sim = MIST / f"{mk['image']}.jpg"
        mistakes.append({**{k: v for k, v in mk.items() if k != "image"},
                         "img": rel(real) if real.exists() else rel(sim), "simulated": not real.exists()})

    manual = [rel(p) for p in sorted(MANUAL.glob("p*.jpg"))] if MANUAL.exists() else []
    ex_file = MANUAL / "exercise_pages.json"
    manual_ex = json.loads(ex_file.read_text(encoding="utf-8")).get("starts", []) if ex_file.exists() else []

    data = {"topics": topics, "specimens": specimens, "mistakes": mistakes, "manual": manual, "manualEx": manual_ex,
            "pageOffset": page_offset(list(meta.values())),
            "exerciseNames": {str(k): v for k, v in EXERCISES.items()}}
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "site_data.js").write_text("window.RS = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    (SITE / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (SITE / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (SITE / "app.js").write_text(APP_JS, encoding="utf-8")
    with open(REPORT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(report[0].keys()))
        w.writeheader()
        w.writerows(report)

    n_photo = sum(1 for s in specimens if s["photo"] and not s["photo"].get("remote"))
    n_remote = sum(1 for s in specimens if s["photo"] and s["photo"].get("remote"))
    print(f"  images from link : {n_remote} (no downloaded copy yet - the browser loads them from the supplied link)")
    print(f"  specimens        : {len(specimens)}  ({n_photo} with their supplied image, {len(specimens) - n_photo} without)")
    print(f"  topics shown     : {', '.join(v['name'] for v in topics.values())}")
    print(f"  manual pages     : {len(manual)}  (printed page = PDF page - {data['pageOffset']})")
    print(f"  report           : {REPORT.relative_to(REPO).as_posix()}")
    print(f"  WEBSITE          : {SITE / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
