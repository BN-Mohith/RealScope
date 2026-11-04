"""
Download (once) the supplied microscope image for every selected specimen.

Reads   Data/selected_specimens.json          (written by Scripts/website/catalog.py from your CSV)
Writes  Data/real_slide_images/cache/<id>.<ext>       one file per distinct link, kept between runs
        Data/real_slide_images/cache_index.json       what each link gave last time (ok / failed + why)
        Data/real_slide_images/photos_manifest.csv    one row per specimen: which file, status, links
        Data/real_slide_images/FAILED_DOWNLOADS.txt   every specimen still without an image, with its link

Downloads happen ONCE. On later runs a link whose file is already in the cache (and still
decodes as an image) is reused without touching the network. A link that failed before is NOT
tried again unless you ask:
    python Scripts/fetch/fetch_real_images.py                 normal: only new / changed links
    python Scripts/fetch/fetch_real_images.py --retry-failed  also retry links that failed before
    python Scripts/fetch/fetch_real_images.py --offline       never use the network (cache only)
    python Scripts/fetch/fetch_real_images.py --force         download every link again

Your own image always wins: save it as  Data/real_slide_images/manual/<image_id>.jpg  or
Data/real_slide_images/manual/<Figure name>.jpg  (e.g. "Metaphase I.jpg"; .png/.webp work too).
Use this for any link a site doesn't allow scripts to download - save it from your browser.

Rules: links to web pages are resolved to the page's main image (Wikimedia/Flickr/Springer figure
pages, short links); logos, icons, error pages and tiny images are rejected; every file is decoded
to prove it is a real image; nothing is replaced by a different picture.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "extraction"))
from common import sha256_of, to_link  # noqa: E402

SELECTED = REPO / "Data" / "selected_specimens.json"
OUT = REPO / "Data" / "real_slide_images"
CACHE = OUT / "cache"
MANUAL = OUT / "manual"
INDEX = OUT / "cache_index.json"
MANIFEST = OUT / "photos_manifest.csv"
FAILED = OUT / "FAILED_DOWNLOADS.txt"

SCRIPT_UA = "RealScope/1.0 (student biology project; python-urllib)"  # honest: this is a script
IMG_EXT = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp",
           "image/gif": ".gif", "image/tiff": ".tif", "image/bmp": ".bmp"}
NOT_A_SPECIMEN = re.compile(r"logo|icon|favicon|sprite|avatar|badge|brand|placeholder|default-image|blank\.", re.I)
MIN_SIDE = 150


# ----------------------------------------------------------------------------- http
def _ssl():
    import ssl
    try:
        import certifi  # fixes CERTIFICATE_VERIFY_FAILED on some machines
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_CTX = None


def http_get(url: str, timeout: float) -> tuple[bytes, str, str]:
    global _CTX
    _CTX = _CTX or _ssl()
    req = urllib.request.Request(url, headers={"User-Agent": SCRIPT_UA, "Accept": "image/*,text/html;q=0.9,*/*;q=0.5"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        data = r.read(40 * 1024 * 1024)
        return data, (r.headers.get("Content-Type") or "").split(";")[0].strip().lower(), r.geturl()


def normalise(url: str) -> str:
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if url.lower().startswith("www."):
        url = "https://" + url
    parts = urllib.parse.urlsplit(url)
    if "utm_" in parts.query:  # tracking tags added when a link is copied - not part of the address
        q = "&".join(kv for kv in parts.query.split("&") if not kv.lower().startswith("utm_"))
        url = urllib.parse.urlunsplit(parts._replace(query=q))
    url = url.replace("://thumb.wikimedia.org/", "://upload.wikimedia.org/")
    m = re.match(r"https?://commons\.(?:m\.)?wikimedia\.org/wiki/(File:[^?#]+)", url)
    if m:  # a Commons file page -> the file itself
        name = urllib.parse.unquote(m.group(1)[5:])
        return "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(name) + "?width=1600"
    return url


def looks_like_image(ctype: str, data: bytes) -> bool:
    return (ctype.startswith("image/") or data[:3] == b"\xff\xd8\xff" or data[:4] == b"\x89PNG"
            or data[8:12] == b"WEBP" or data[:4] in (b"GIF8", b"II*\x00", b"MM\x00*"))


def ext_for(ctype: str, data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return ".png"
    if data[8:12] == b"WEBP":
        return ".webp"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    return IMG_EXT.get(ctype, ".jpg")


def image_in_page(page: str, base: str) -> str | None:
    """The main specimen image of a web page - never a logo/icon."""
    import html as H
    m = re.search(r"/figures/(\d+)", base)   # Springer/Nature figure page: that figure, not figure 1
    if m:
        f = re.search(r'(https?:)?//[^"\'\s]+?Fig%s_HTML\.(?:png|jpe?g|gif|webp)' % m.group(1), page)
        if f:
            u = f.group(0)
            return ("https:" + u) if u.startswith("//") else u
    pats = [r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
            r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)',
            r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)']
    for p in pats:
        for m in re.finditer(p, page, re.I):
            u = urllib.parse.urljoin(base, H.unescape(m.group(1)))
            if not NOT_A_SPECIMEN.search(u):
                return u
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+\.(?:jpe?g|png|webp)[^"\']*)', page, re.I):
        u = urllib.parse.urljoin(base, H.unescape(m.group(1)))
        if not NOT_A_SPECIMEN.search(u):
            return u
    return None


def decode_size(data: bytes):
    import cv2
    import numpy as np
    im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    return None if im is None else (int(im.shape[1]), int(im.shape[0]))


def download(link: str, timeout: float) -> dict:
    """Returns {data, ext, resolved, w, h}; raises ValueError/URLError with a readable reason."""
    url = normalise(link)
    data, ctype, final = http_get(url, timeout)
    from_page = False
    if not looks_like_image(ctype, data):
        text = data[:200000].decode("utf-8", "replace")
        if "html" not in ctype and "<html" not in text[:500].lower() and "<!doctype" not in text[:500].lower():
            raise ValueError(f"the link returned '{ctype or 'unknown'}', not an image")
        img = image_in_page(text, final)
        if not img:
            title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
            raise ValueError("the link returned a web page without a usable image"
                             + (f" (page title: '{' '.join(title.group(1).split())[:60]}')" if title else ""))
        data, ctype, final = http_get(normalise(img), timeout)
        from_page = True
        if not looks_like_image(ctype, data):
            raise ValueError(f"the page's image link returned '{ctype or 'unknown'}', not an image")
    size = decode_size(data)
    if size is None:
        raise ValueError("the file does not decode as an image")
    if min(size) < MIN_SIDE:
        raise ValueError(f"image is only {size[0]}x{size[1]} px - too small to be the specimen photo")
    if from_page and NOT_A_SPECIMEN.search(final):
        raise ValueError(f"the page only offered a logo/icon ({final})")
    ext = ext_for(ctype, data)
    if ext in (".tif", ".bmp", ".gif"):  # browsers can't show TIFF: same pixels, stored as PNG
        import cv2
        import numpy as np
        ok, buf = cv2.imencode(".png", cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR))
        data, ext = buf.tobytes(), ".png"
    return {"data": data, "ext": ext, "resolved": final, "w": size[0], "h": size[1]}


def reason(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        if e.code in (401, 403, 429):
            return f"HTTP {e.code}: the site does not allow downloads by scripts - save the image yourself into the manual folder"
        if e.code in (404, 410):
            return f"HTTP {e.code}: the link is broken or has expired"
        return f"HTTP {e.code} {e.reason}: the site returned an error (it may be temporarily down)"
    if isinstance(e, urllib.error.URLError):
        return f"could not reach the site ({e.reason})"
    if isinstance(e, TimeoutError):
        return "the site did not answer in time"
    return str(e) or type(e).__name__


# ----------------------------------------------------------------------------- cache
def url_key(url: str) -> str:
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


def load_index() -> dict:
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}


def cached_ok(entry: dict | None) -> bool:
    if not entry or entry.get("status") != "ok":
        return False
    p = REPO / entry.get("file", "")
    if not p.exists() or sha256_of(p) != entry.get("sha256"):
        return False
    return decode_size(p.read_bytes()) is not None


def own_file(spec: dict) -> Path | None:
    def n(s):
        return re.sub(r"[^a-z0-9]+", "", s.lower())
    if not MANUAL.exists():
        return None
    for p in sorted(MANUAL.iterdir()):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and n(p.stem) in (n(spec["image_id"]), n(spec["figure"])):
            return p
    return None


# ----------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retry-failed", action="store_true", help="try links that failed on an earlier run again")
    ap.add_argument("--offline", action="store_true", help="no network - use cached images only")
    ap.add_argument("--force", action="store_true", help="download every link again")
    ap.add_argument("--timeout", type=float, default=25)
    args = ap.parse_args(argv)
    if not SELECTED.exists():
        sys.exit("[X] Data/selected_specimens.json missing - run Scripts/website/catalog.py first.")
    specs = json.loads(SELECTED.read_text(encoding="utf-8"))["specimens"]
    for d in (CACHE, MANUAL):
        d.mkdir(parents=True, exist_ok=True)
    index = load_index()
    now = datetime.datetime.now().isoformat(timespec="seconds")

    links = []
    for s in specs:
        if s["link"] and s["link"] not in links and not own_file(s):
            links.append(s["link"])
    stats = {"reused": 0, "downloaded": 0, "failed": 0, "skipped": 0}
    for link in links:
        entry = index.get(link)
        short = (link[:70] + "...") if len(link) > 73 else link
        if not args.force and cached_ok(entry):
            stats["reused"] += 1
            continue
        if not re.match(r"(?i)^(https?://|//|www\.)", link):
            index[link] = {"status": "failed", "error": "the cell has text, not a web link", "checked": now}
            stats["failed"] += 1
            continue
        if args.offline or (entry and entry.get("status") == "failed" and entry.get("permanent", True)
                            and not (args.retry_failed or args.force)):
            stats["skipped"] += 1
            continue
        try:
            got = download(link, args.timeout)
            dest = CACHE / (url_key(link) + got["ext"])
            for old in CACHE.glob(url_key(link) + ".*"):
                old.unlink()
            dest.write_bytes(got["data"])
            index[link] = {"status": "ok", "file": to_link(dest), "sha256": sha256_of(dest), "resolved_url": got["resolved"],
                           "w": got["w"], "h": got["h"], "checked": now}
            stats["downloaded"] += 1
            print(f"  downloaded  {got['w']}x{got['h']}  {short}")
        except Exception as e:
            # network trouble / server errors are retried automatically next run; refusals, dead links,
            # error pages and non-images are only retried with --retry-failed
            transient = (isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError))
                         and not (isinstance(e, urllib.error.HTTPError) and e.code < 500 and e.code != 429))
            index[link] = {"status": "failed", "error": reason(e), "permanent": not transient, "checked": now}
            stats["failed"] += 1
            print(f"  FAILED      {short}\n              {index[link]['error']}")
        time.sleep(0.4)

    # forget links that are no longer in the CSV, and delete their cached files
    current = {s["link"] for s in specs}
    for link in [k for k in index if k not in current]:
        index.pop(link)
    keep = {Path(e["file"]).name for e in index.values() if e.get("status") == "ok" and e.get("file")}
    for p in CACHE.iterdir():
        if p.name not in keep:
            p.unlink()
    INDEX.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")

    rows, missing = [], []
    for s in specs:
        r = {"csv_no": s["csv_no"], "figure": s["figure"], "image_id": s["image_id"], "supplied_link": s["link"],
             "resolved_url": "", "status": "", "file": "", "width_px": "", "height_px": "", "licence": s["licence"], "note": ""}
        own = own_file(s)
        e = index.get(s["link"], {})
        if own:
            size = decode_size(own.read_bytes())
            if size:
                r.update(status="ok", file=to_link(own), width_px=size[0], height_px=size[1], note="your own file (manual folder)")
            else:
                r.update(status="failed", note=f"{own.name} in the manual folder is not a readable image")
        elif not s["link"]:
            r.update(status="no_link", note="no image link in the CSV")
        elif e.get("status") == "ok" and (REPO / e["file"]).exists():
            r.update(status="ok", file=e["file"], resolved_url=e.get("resolved_url", ""), width_px=e.get("w", ""), height_px=e.get("h", ""))
        elif e.get("status") == "failed":
            r.update(status="failed", note=e.get("error", ""))
        else:
            r.update(status="not_downloaded", note="not downloaded yet (offline run)")
        if s.get("link_warning") and r["status"] == "ok" and not own:
            r.update(status="held_back", note=s["link_warning"] + " - not shown until the CSV link is checked")
        if r["status"] != "ok":
            missing.append(r)
        rows.append(r)

    with open(MANIFEST, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["csv_no"])
        w.writeheader()
        w.writerows(rows)
    if missing:
        lines = ["Specimens without a supplied image yet.",
                 "Fix: correct the link in Data/input/specimens.csv, or save the image yourself (from your browser) as",
                 f"    {MANUAL / '<image_id or figure name>.jpg'}     e.g. {missing[0]['image_id']}.jpg",
                 "then run Scripts/run_all.py again. Network/server errors are retried automatically;",
                 "for links the site refused or that gave no image, add --retry-failed to try them again.", ""]
        for r in missing:
            lines += [f"Row {r['csv_no']:>3}  {r['figure']}  ({r['image_id']})",
                      f"         link : {r['supplied_link'] or '(none)'}",
                      f"         why  : {r['note'] or r['status']}"]
        FAILED.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif FAILED.exists():
        FAILED.unlink()

    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"  links          : {len(links)} distinct  (reused from cache {stats['reused']}, downloaded {stats['downloaded']}, "
          f"failed {stats['failed']}, not tried {stats['skipped']})")
    print(f"  specimens      : {ok} of {len(rows)} have a supplied image")
    if missing:
        print(f"  still missing  : {len(missing)} - see {FAILED.relative_to(REPO).as_posix()}")
        if stats["skipped"] and not args.offline:
            print("                   (links that failed before were not retried - use --retry-failed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
