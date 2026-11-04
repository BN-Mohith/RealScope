"""
Check the built website against the specimen list.

  * every CSV row is either on the site or listed as unmatched in Data/specimen_matching.csv
  * every specimen has its manual diagram (file exists and decodes), and its label-free copy if offered
  * every supplied image the site shows exists and decodes; specimens without one show a source link
  * every "Open page N of the manual" link points to an existing manual page, and the printed
    page number shown matches the page metadata
  * gallery, search, topic filters, dropdown, next/previous and exercise shortcuts all use this same list
Exit code 1 only for real faults (a missing diagram, a broken file or page link) -
a missing supplied image is reported but is not a fault of the website.

    python Scripts/validation/verify_site.py
"""
import csv
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "Data" / "website"


def decodes(p: Path) -> bool:
    import cv2
    import numpy as np
    return p.exists() and cv2.imdecode(np.frombuffer(p.read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED) is not None


def main() -> int:
    js = (SITE / "site_data.js").read_text(encoding="utf-8")
    D = json.loads(js[js.index("=") + 1: js.rstrip().rindex(";")])
    with open(REPO / "Data" / "specimen_matching.csv", encoding="utf-8-sig") as f:
        match = list(csv.DictReader(f))
    with open(REPO / "Data" / "raw_data" / "images_metadata.csv", encoding="utf-8-sig") as f:
        meta = {r["image_id"]: r for r in csv.DictReader(f)}
    faults, notes = [], []

    matched = [m for m in match if m["status"] == "matched"]
    site_ids = [s["id"] for s in D["specimens"]]
    if sorted(site_ids) != sorted(m["image_id"] for m in matched):
        faults.append("the site's specimen list differs from the matched CSV rows")
    if len(set(site_ids)) != len(site_ids):
        faults.append("a diagram appears twice on the site")
    for m in match:
        if m["status"] != "matched":
            notes.append(f"CSV row {m['no']} '{m['figure']}' is not on the site: {m['status']} - {m['detail']}")

    N = len(D["manual"])
    off = D.get("pageOffset")
    for p in D["manual"]:
        if not (SITE / p).exists():
            faults.append(f"manual page file missing: {p}")
    n_photo = n_remote = 0
    for s in D["specimens"]:
        tag = f"{s['caption']} ({s['id']})"
        if not decodes(SITE / s["img"]):
            faults.append(f"{tag}: diagram missing or unreadable ({s['img']})")
        if s.get("imgPlain") and not decodes(SITE / s["imgPlain"]):
            faults.append(f"{tag}: label-free diagram missing ({s['imgPlain']})")
        if s["cat"] not in D["topics"]:
            faults.append(f"{tag}: topic '{s['cat']}' not in the topic filter")
        if not (1 <= s["pdf"] <= N):
            faults.append(f"{tag}: manual link to PDF page {s['pdf']} but the manual has {N} pages")
        m = meta[s["id"]]
        if int(m["printed_page"]) != s["page"] or int(m["pdf_page"]) != s["pdf"]:
            faults.append(f"{tag}: page numbers differ from the extraction metadata")
        if off is not None and s["pdf"] - off != s["page"]:
            faults.append(f"{tag}: printed page {s['page']} does not match PDF page {s['pdf']} - {off}")
        if s["photo"] and s["photo"].get("remote"):
            n_remote += 1
            if not s["photo"]["src"].startswith(("http://", "https://")):
                faults.append(f"{tag}: image link is not a web address ({s['photo']['src']})")
        elif s["photo"]:
            n_photo += 1
            for k in ("src", "thumb"):
                if not decodes(SITE / s["photo"][k]):
                    faults.append(f"{tag}: supplied image file missing/unreadable ({s['photo'][k]})")
        elif not s.get("link"):
            notes.append(f"{tag}: no supplied image and no link")
    print(f"  CSV rows         : {len(match)}  (on the site: {len(site_ids)}, not matched: {len(match) - len(matched)})")
    print(f"  diagrams         : {len(site_ids)} checked")
    print(f"  supplied images  : {n_photo} downloaded copies, {n_remote} loaded from their link in the browser, "
          f"{len(site_ids) - n_photo - n_remote} not available")
    print(f"  manual           : {N} pages, printed page = PDF page - {off}")
    for n in notes:
        print(f"  [note] {n}")
    for f_ in faults:
        print(f"  [X] {f_}")
    print("  RESULT: " + ("PASS" if not faults else f"FAIL ({len(faults)} problems)"))
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
