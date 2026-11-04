"""
RealScope - build everything with one command and open the website.

    python Scripts/run_all.py                 (VS Code: open this file and press Run)

Steps (each one is skipped when its inputs have not changed):
  0. Check setup: Python, packages, Tesseract OCR, Source/lab_manual.pdf, Data/input/specimens.csv
  1. Read the specimen CSV -> which printed manual pages are needed
  2. Extract those pages + cut out the diagrams        (Data/raw_data/)            - cached
  3. Verify the extraction (pixel-identical crops)                                 - when re-extracted
  4. Match every CSV row to its diagram by page + name  (Data/specimen_matching.csv)
  5. Download the supplied images ONCE                  (Data/real_slide_images/)   - cached
  6. Website images: straightened diagrams, label-free copies, manual pages        - cached
  7. Mistakes-page pictures (simulated)                                            - cached
  8. Build the website                                  (Data/website/index.html)
  9. Check the website (every specimen, image, page link)
 10. Open it in your browser

Options
  --install        install missing Python packages first
  --offline        no internet: use only images already downloaded
  --retry-failed   try image links that failed on an earlier run again
  --refetch        download every image again
  --rebuild        redo everything (ignore all caches)
  --no-open        don't open the browser at the end

Everything printed is also saved to Data/run_log.txt.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "Scripts"
DATA = REPO / "Data"
PDF = REPO / "Source" / "lab_manual.pdf"
CSV_IN = DATA / "input" / "specimens.csv"
STATE = DATA / "raw_data" / "extraction_state.json"
LOG = DATA / "run_log.txt"
PACKAGES = {"pymupdf": "pymupdf", "cv2": "opencv-python-headless", "numpy": "numpy",
            "pytesseract": "pytesseract", "certifi": "certifi"}
EXTRACTION_SETTINGS = {"numbering": "printed", "groups": True, "version": 2}

_lines: list[str] = []


def say(msg: str = "") -> None:
    print(msg, flush=True)
    _lines.append(msg)


def header(t: str) -> None:
    say("")
    say("=" * 72)
    say(t)
    say("=" * 72)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(script: str, args: list[str] | None = None) -> bool:
    cmd = [sys.executable, "-u", str(SCRIPTS / script)] + (args or [])
    say("$ python " + " ".join([f"Scripts/{script}"] + (args or [])))
    start = datetime.datetime.now()
    proc = subprocess.Popen(cmd, cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    for line in proc.stdout:
        say(line.rstrip("\n"))
    code = proc.wait()
    secs = (datetime.datetime.now() - start).total_seconds()
    if code:
        say(f"[X] {script} failed (exit code {code}) - the error is just above.")
        return False
    say(f"[OK] {secs:.0f}s")
    return True


# ----------------------------------------------------------------------------- setup
def check_setup(install: bool) -> bool:
    header("STEP 0 - checking your setup")
    ok = True
    say(f"Python  : {sys.version.split()[0]}  ({sys.executable})")
    say(f"System  : {platform.system()} {platform.release()}")
    say(f"Project : {REPO}")
    if sys.version_info < (3, 9):
        say("  [X] Python 3.9 or newer is needed (3.14 recommended) - python.org/downloads")
        ok = False
    missing = []
    for mod, pip in PACKAGES.items():
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(pip)
    if missing and install:
        say("  -> installing " + ", ".join(missing))
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(REPO / "requirements.txt")],
                           capture_output=True, text=True)
        say(r.stdout[-1500:] + r.stderr[-1500:])
        importlib.invalidate_caches()
        missing = [p for m, p in PACKAGES.items() if importlib.util.find_spec(m) is None]
    if missing:
        say(f"  [X] missing Python packages: {', '.join(missing)}")
        say(f"      FIX: python -m pip install -r requirements.txt     (or: python Scripts/run_all.py --install)")
        ok = False
    else:
        say("  [OK] Python packages")

    sys.path.insert(0, str(SCRIPTS / "extraction"))
    try:
        from common import configure_tesseract
        if not configure_tesseract():
            raise RuntimeError
        import pytesseract
        say(f"  [OK] Tesseract OCR {pytesseract.get_tesseract_version()}")
    except Exception:
        say("  [X] Tesseract OCR (a separate program, not a pip package) was not found.")
        if platform.system() == "Windows":
            say("      FIX: install it from https://github.com/UB-Mannheim/tesseract/wiki")
            say("           keep the default folder C:\\Program Files\\Tesseract-OCR, then reopen VS Code.")
        elif platform.system() == "Darwin":
            say("      FIX: brew install tesseract")
        else:
            say("      FIX: sudo apt install tesseract-ocr")
        say("      If it is installed elsewhere, set the environment variable TESSERACT_CMD to tesseract.exe")
        ok = False

    if PDF.exists():
        say(f"  [OK] {PDF.relative_to(REPO).as_posix()} ({PDF.stat().st_size / 1e6:.1f} MB)")
    else:
        say(f"  [X] {PDF.relative_to(REPO).as_posix()} not found - put the lab manual there with exactly that name")
        ok = False
    csvs = [CSV_IN] if CSV_IN.exists() else sorted((DATA / "input").glob("*.csv")) if (DATA / "input").exists() else []
    if csvs:
        say(f"  [OK] specimen list {csvs[0].relative_to(REPO).as_posix()}")
    else:
        say(f"  [X] specimen list not found - put your CSV at {CSV_IN.relative_to(REPO).as_posix()}")
        ok = False
    return ok


# ----------------------------------------------------------------------------- extraction cache
def extraction_fingerprint(pages: list[int]) -> dict:
    scripts = ["extraction/common.py", "extraction/extract_pages.py", "extraction/extract_images_from_pages.py"]
    return {"pdf_sha256": sha256(PDF), "printed_pages": pages, "settings": EXTRACTION_SETTINGS,
            "scripts": {s: sha256(SCRIPTS / s) for s in scripts}}


def extraction_is_current(fp: dict) -> bool:
    try:
        old = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return False
    if old.get("fingerprint") != fp or not old.get("verified"):
        return False
    import csv
    meta = DATA / "raw_data" / "images_metadata.csv"
    if not meta.exists():
        return False
    with open(meta, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return bool(rows) and all((REPO / r["image_link"]).exists() for r in rows)


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    say(f"RealScope build - {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    if not check_setup(a.install):
        say("\nSetup is not complete - fix the [X] items above, then run this again.")
        return 1

    header("STEP 1 - pages needed by the specimen list")
    sys.path.insert(0, str(SCRIPTS / "website"))
    from catalog import find_csv, read_rows, selected_pages
    rows = read_rows(find_csv())
    pages = selected_pages()
    say(f"  {len(rows)} specimens on {len(pages)} printed pages: {', '.join(map(str, pages))}")

    header("STEP 2-3 - extract pages and diagrams from the manual")
    fp = extraction_fingerprint(pages)
    if not a.rebuild and extraction_is_current(fp):
        say("  [cache] PDF, page list and extraction settings unchanged - reusing Data/raw_data/")
    else:
        STATE.unlink(missing_ok=True)
        for d in ("extracted_pages", "extracted_images", "review_overlays"):  # no stale files from an older page list
            shutil.rmtree(DATA / "raw_data" / d, ignore_errors=True)
        page_arg = ",".join(map(str, pages))
        if not run("extraction/extract_pages.py", ["--pages", page_arg, "--numbering", "printed"]):
            return 1
        if not run("extraction/extract_images_from_pages.py"):
            return 1
        if not run("validation/verify_outputs.py", ["--sheet"]):
            return 1
        STATE.write_text(json.dumps({"fingerprint": fp, "verified": True,
                                     "at": datetime.datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")

    header("STEP 4 - match specimens to diagrams (by printed page + name)")
    if not run("website/catalog.py"):
        return 1

    header("STEP 5 - supplied images (downloaded once, then reused)")
    fetch_args = (["--offline"] if a.offline else []) + (["--retry-failed"] if a.retry_failed else []) + \
                 (["--force"] if a.refetch else [])
    if not run("fetch/fetch_real_images.py", fetch_args):
        return 1

    header("STEP 6-7 - website images")
    if not run("website/prepare_display_images.py", ["--force"] if a.rebuild else []):
        return 1
    if not run("website/make_mistake_images.py", ["--force"] if a.rebuild else []):
        return 1

    header("STEP 8 - build the website")
    if not run("website/build_website.py"):
        return 1

    header("STEP 9 - check the website")
    if not run("validation/verify_site.py"):
        return 1

    site = DATA / "website" / "index.html"
    header("DONE")
    say(f"  Website            : {site}")
    say(f"  Matching report    : {DATA / 'specimen_matching.csv'}")
    say(f"  Images still missing (if any): {DATA / 'real_slide_images' / 'FAILED_DOWNLOADS.txt'}")
    if not a.no_open:
        import webbrowser
        webbrowser.open(site.as_uri())
        say("  (opened in your browser)")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        say("\nStopped.")
        code = 1
    except Exception:
        import traceback
        say("\n[X] Unexpected error:\n" + traceback.format_exc())
        code = 1
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    except Exception:
        pass
    sys.exit(code)
