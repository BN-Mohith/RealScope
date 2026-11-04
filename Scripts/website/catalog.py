"""
The specimen list: which specimens the website shows, and which manual diagram each one is.

Reads   Data/input/specimens.csv          YOUR list (the only authority on what is included)
        Data/raw_data/images_metadata.csv the diagrams cut out of the manual (steps 1-2)
Writes  Data/specimen_matching.csv        one row per CSV row: matched diagram, how, or why not
        Data/selected_specimens.json      the matched list, used by the fetch and website steps

How a CSV row is matched to a diagram
  * Only diagrams on the SAME printed manual page are candidates.
  * Names are compared after normalising harmless differences: case, punctuation, hyphens,
    spacing, "T.S./L.S./V.S. of" prefixes, a trailing "stage", and text in brackets.
  * Each diagram's known names = its display name, the caption printed in the manual and
    the extra names in site_content.NAME_ALIASES.
  * Exact name match first; otherwise a word-overlap match only if it is clearly the best one.
  * Anything ambiguous or unmatched is REPORTED and left out - never assigned to a neighbour.
The CSV row number ("No.") is only used for messages: deleting or re-ordering rows never
changes which diagram a specimen gets.

    python Scripts/website/catalog.py
    python Scripts/website/catalog.py --csv "Data/input/My list.csv"
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "website"))
from site_content import NAME_ALIASES, SPECIMENS  # noqa: E402

INPUT_DIR = REPO / "Data" / "input"
META_CSV = REPO / "Data" / "raw_data" / "images_metadata.csv"
MATCH_CSV = REPO / "Data" / "specimen_matching.csv"
SELECTED = REPO / "Data" / "selected_specimens.json"


# ----------------------------------------------------------------------------- reading the CSV
def find_csv(arg: str | None = None) -> Path:
    if arg:
        p = Path(arg)
        p = p if p.is_absolute() else REPO / p
        if not p.exists():
            sys.exit(f"[X] CSV not found: {p}")
        return p
    if (INPUT_DIR / "specimens.csv").exists():
        return INPUT_DIR / "specimens.csv"
    found = sorted(INPUT_DIR.glob("*.csv")) if INPUT_DIR.exists() else []
    if not found:
        sys.exit(f"[X] No specimen CSV found. Put it at {INPUT_DIR / 'specimens.csv'}")
    return found[0]


def _clean(v) -> str:
    """Trim accidental whitespace (incl. tabs/newlines inside a cell) without changing the text."""
    return " ".join(str(v or "").split())


def read_rows(path: Path) -> list[dict]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.reader(io.StringIO(text)))
    head_i = next((i for i, r in enumerate(rows)
                   if any(c.strip().lower().startswith("no") for c in r) and any("link" in c.lower() for c in r)), None)
    if head_i is None:
        sys.exit("[X] The CSV needs a header row with 'No.', 'Manual page', 'Figure' and a '... Links ...' column.")
    head = [h.strip().lower() for h in rows[head_i]]

    def col(*keys, exclude=()):
        return next((j for j, h in enumerate(head) if all(k in h for k in keys) and not any(x in h for x in exclude)), None)

    c = {"no": col("no"), "page": col("manual", "page"), "figure": col("figure"),
         "mag": col("magnif"), "link": col("link", exclude=("suggest",)), "lic": col("lic")}
    if c["page"] is None or c["figure"] is None or c["link"] is None:
        sys.exit(f"[X] CSV columns not recognised: {rows[head_i]}")
    out = []
    for line_no, r in enumerate(rows[head_i + 1:], start=head_i + 2):
        get = lambda k: _clean(r[c[k]]) if c[k] is not None and c[k] < len(r) else ""
        if not get("figure") and not get("page") and not get("link"):
            continue  # empty trailing row
        try:
            page = int(float(get("page")))
        except ValueError:
            page = None
        out.append({"csv_line": line_no, "no": get("no"), "manual_page": page, "figure": get("figure"),
                    "magnification": get("mag"), "link": get("link"), "licence_raw": get("lic")})
    return out


def clean_licence(text: str) -> str:
    """Licence/credit text as supplied, minus stray HTML tags/backticks pasted into the cell."""
    t = re.sub(r"<a\s[^>]*>(.*?)</a>", r"\1", text, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", "", t).replace("`", "")
    return " ".join(t.split()).strip(" ,;")


# ----------------------------------------------------------------------------- matching
def norm(name: str, drop_brackets: bool = False) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    if drop_brackets:
        s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b([tlv])\s*\.?\s*s\s*\.?(?=\s|$|\W)", r" \1s ", s)       # T.S. / t s / TS -> ts
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"^\s*(ts|ls|vs)\s+of\s+", " ", s)                            # "ts of anther" -> "anther"
    s = re.sub(r"\b(ts|ls|vs)\b", " ", s)
    s = re.sub(r"\bstage\b\s*$", " ", s.strip())
    return " ".join(s.split())


def name_keys(image_id: str, meta_caption: str) -> set[str]:
    names = [SPECIMENS.get(image_id, {}).get("caption", ""), meta_caption] + NAME_ALIASES.get(image_id, [])
    keys = set()
    for n in names:
        if n:
            keys.add(norm(n))
            keys.add(norm(n, drop_brackets=True))
    keys.discard("")
    return keys


def overlap(a: str, b: str) -> float:
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A and B else 0.0


def build_catalog(csv_path: Path) -> tuple[list[dict], list[dict]]:
    if not META_CSV.exists():
        sys.exit("[X] images_metadata.csv not found - run the extraction (Scripts/run_all.py) first.")
    with open(META_CSV, encoding="utf-8-sig", newline="") as f:
        figs = [r for r in csv.DictReader(f) if r["image_type"] == "figure"]
    by_page: dict[int, list[dict]] = {}
    for r in figs:
        by_page.setdefault(int(r["printed_page"]), []).append(r)

    rows = read_rows(csv_path)
    report, chosen = [], {}
    for row in rows:
        rec = {**row, "image_id": "", "method": "", "score": "", "status": "", "detail": ""}
        cands = by_page.get(row["manual_page"] or -1, [])
        if not row["figure"]:
            rec.update(status="unmatched", detail="no figure name")
        elif not cands:
            rec.update(status="unmatched", detail=f"no diagrams were extracted from printed page {row['manual_page']}")
        else:
            want = {norm(row["figure"]), norm(row["figure"], drop_brackets=True)} - {""}
            exact = [c for c in cands if want & name_keys(c["image_id"], c["caption"])]
            if len(exact) == 1:
                rec.update(image_id=exact[0]["image_id"], method="name", score="1.00", status="matched")
            elif len(exact) > 1:
                rec.update(status="ambiguous", detail="same name as " + ", ".join(c["image_id"] for c in exact))
            else:
                scored = sorted(((max(overlap(w, k) for w in want for k in name_keys(c["image_id"], c["caption"])), c)
                                 for c in cands), key=lambda t: -t[0])
                best = scored[0]
                second = scored[1][0] if len(scored) > 1 else 0.0
                if best[0] >= 0.6 and best[0] - second >= 0.2:
                    rec.update(image_id=best[1]["image_id"], method="closest name", score=f"{best[0]:.2f}", status="matched")
                else:
                    near = "; ".join(f"{c['image_id']} ({s:.2f})" for s, c in scored[:3])
                    rec.update(status="unmatched", detail=f"no clear match on page {row['manual_page']} - nearest: {near}. "
                                                          f"Add the name to NAME_ALIASES in site_content.py")
        if rec["status"] == "matched":
            if rec["image_id"] in chosen:
                other = chosen[rec["image_id"]]
                rec.update(status="duplicate", detail=f"same diagram as CSV row {other['no']} ({other['figure']})")
            else:
                chosen[rec["image_id"]] = rec
        report.append(rec)

    # the same supplied link used for two different specimens is almost always a copy-paste slip
    by_link: dict[str, list[dict]] = {}
    for rec in report:
        if rec["status"] == "matched" and rec["link"]:
            by_link.setdefault(rec["link"].strip(), []).append(rec)
    for link, recs in by_link.items():
        if len({norm(r["figure"]) for r in recs}) > 1:
            # keep the row whose name is in the link (e.g. ".../Amoeba_proteus.jpg" -> Amoeba);
            # if the link names none of them, hold all of them back until the CSV is checked
            flat = re.sub(r"[^a-z0-9]+", " ", urllib.parse.unquote(link).lower())
            named = [r for r in recs if all(w in flat for w in norm(r["figure"], drop_brackets=True).split())]
            for r in recs:
                if len(named) == 1 and r is named[0]:
                    continue
                others = ", ".join(f"row {o['no']} {o['figure']}" for o in recs if o is not r)
                r["link_warning"] = f"the same image link is also given for {others}"

    selected = []
    for rec in report:
        if rec["status"] != "matched":
            continue
        m = next(f for f in figs if f["image_id"] == rec["image_id"])
        selected.append({
            "image_id": rec["image_id"], "csv_no": rec["no"], "figure": rec["figure"],
            "manual_page": rec["manual_page"], "pdf_page": int(m["pdf_page"]),
            "magnification": rec["magnification"], "link": rec["link"],
            "licence": clean_licence(rec["licence_raw"]), "link_warning": rec.get("link_warning", ""),
        })
    return report, selected


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", help="specimen CSV (default: Data/input/specimens.csv)")
    args = ap.parse_args(argv)
    path = find_csv(args.csv)
    report, selected = build_catalog(path)

    MATCH_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = ["no", "manual_page", "figure", "status", "image_id", "method", "score", "detail", "link_warning", "link"]
    with open(MATCH_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(report)
    SELECTED.write_text(json.dumps({"csv": path.name, "specimens": selected}, indent=1, ensure_ascii=False), encoding="utf-8")

    pages = sorted({r["manual_page"] for r in report if r["manual_page"]})
    bad = [r for r in report if r["status"] != "matched"]
    print(f"  CSV            : {path.relative_to(REPO).as_posix()}  ({len(report)} specimens, {len(pages)} printed pages)")
    print(f"  matched        : {len(selected)}  ({sum(1 for r in report if r['method'] == 'closest name')} by closest name)")
    for r in bad:
        print(f"  [!] row {r['no']} '{r['figure']}' (p.{r['manual_page']}): {r['status']} - {r['detail']}")
    for s in selected:
        if s["link_warning"]:
            print(f"  [!] row {s['csv_no']} '{s['figure']}': {s['link_warning']}")
    print(f"  report         : {MATCH_CSV.relative_to(REPO).as_posix()}")
    return 0


def selected_pages(csv_arg: str | None = None) -> list[int]:
    """Printed pages named in the CSV - used by run_all.py to decide what to extract."""
    return sorted({r["manual_page"] for r in read_rows(find_csv(csv_arg)) if r["manual_page"]})


if __name__ == "__main__":
    sys.exit(main())
