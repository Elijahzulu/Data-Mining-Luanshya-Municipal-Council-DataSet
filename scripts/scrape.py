"""
Scraper for Luanshya Municipal Council (https://www.luanshyacouncil.gov.zm/).

KNOWN ISSUE — the council's TLS certificate is currently expired/invalid:
requests to www.luanshyacouncil.gov.zm fail certificate validation
("not within its validity period"). This was confirmed to be a problem
with THEIR server, not the calling machine: other hosts (e.g. the ECZ
source in sources_seed.csv) verify normally in the same run. Because this
only ever does read-only GETs of public documents (no login, no data sent
beyond a URL), certificate verification is disabled for that one host
specifically (see UNVERIFIED_HOSTS below) — every other host is still
verified normally. Mention this in the Data in Brief paper as a data-
provenance caveat; re-enable verification for this host once they fix it.

What it does:
  1. Reads data/raw/sources_seed.csv (a hand-curated list of known pages/PDFs
     found via search, since the nav couldn't be crawled live from the
     sandbox) and downloads each one as-is.
  2. Crawls the WordPress "Publications" page (?page_id=959) and the "CDF"
     page (?page_id=3525) for any additional wp-content/uploads/*.pdf links
     not already in the seed list.
  3. Walks the news archive (WordPress ?p=<id> posts and /page/N/ pagination
     from the homepage) to pick up council notices / resolutions / CDF
     project announcements as HTML.
  4. Saves everything untouched under data/raw/ :
       data/raw/pages/<page_id or slug>.html
       data/raw/pdfs/<original-filename>.pdf
       data/raw/news/p<id>.html
     plus a manifest data/raw/manifest.csv recording what was fetched, when,
     and the HTTP status, so re-runs are resumable and auditable.

Usage:
    pip install requests beautifulsoup4
    python scripts/scrape.py

Be polite: this sleeps briefly between requests and identifies itself via
User-Agent so the council's small server isn't hammered. It's also safe to
re-run after an interruption — anything already downloaded is skipped.
"""
from __future__ import annotations

import csv
import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
import urllib3
from bs4 import BeautifulSoup

# Hosts whose certificate is known-broken (see module docstring). Verification
# is skipped ONLY for requests to these hosts; every other host is verified
# normally.
UNVERIFIED_HOSTS = {"www.luanshyacouncil.gov.zm", "luanshyacouncil.gov.zm"}

BASE = "https://www.luanshyacouncil.gov.zm/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; UNZA-CSC4792-Team9-ResearchBot/1.0; "
        "academic open-data project; contact: philsamakayi@gmail.com)"
    )
}
SLEEP_SECONDS = 1.5
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 5  # seconds; multiplied by attempt number

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PAGES_DIR = RAW / "pages"
PDFS_DIR = RAW / "pdfs"
NEWS_DIR = RAW / "news"
SEED_CSV = RAW / "sources_seed.csv"
MANIFEST_CSV = RAW / "manifest.csv"

# Pages known (from the homepage nav) to be worth crawling for more PDF links.
CRAWL_FOR_LINKS = [
    "https://www.luanshyacouncil.gov.zm/?page_id=959",   # Publications
    "https://www.luanshyacouncil.gov.zm/?page_id=3525",  # CDF
]

# How many news-archive pages to walk looking for ?p=NNNN post links.
NEWS_ARCHIVE_PAGES = 15

# The council names some PDFs very verbosely (100+ chars). Windows' default
# MAX_PATH is 260 characters for the *whole* path, and a project folder
# nested inside a synced drive (OneDrive/Google Drive export, etc.) can
# easily eat 150+ of those on its own — leaving too little room for a long
# filename. Cap filenames well under that so the scraper doesn't crash
# partway through a run just because of where the repo happens to be checked
# out.
MAX_FILENAME_LEN = 100


@dataclass
class FetchResult:
    url: str
    local_path: str
    status: int
    content_type: str
    bytes: int


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _verify_for(url: str) -> bool:
    """False only for hosts with a known-broken certificate (see docstring)."""
    return urlparse(url).netloc not in UNVERIFIED_HOSTS


def _shorten_filename(name: str, url: str) -> str:
    """Truncate an overly-long filename, keeping it unique by appending a
    short hash of the source URL. See MAX_FILENAME_LEN above for why."""
    if len(name) <= MAX_FILENAME_LEN:
        return name
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        ext = "." + ext
    else:
        stem, ext = name, ""
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    keep = max(1, MAX_FILENAME_LEN - len(ext) - len(digest) - 1)
    return f"{stem[:keep]}-{digest}{ext}"


def _safe_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path and parsed.path not in ("", "/"):
        name = parsed.path.rstrip("/").split("/")[-1]
        if name:
            return _shorten_filename(name, url)
    qs = parse_qs(parsed.query)
    if "page_id" in qs:
        return f"page_{qs['page_id'][0]}.html"
    if "p" in qs:
        return f"p{qs['p'][0]}.html"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", url)[-80:] + ".html"


def _get_with_retry(session: requests.Session, url: str) -> requests.Response | None:
    """GET with a few retries + backoff, so a mid-run network drop (DNS
    failure, connection reset, timeout) doesn't kill the whole crawl — it
    just costs some seconds before moving on."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return session.get(url, timeout=TIMEOUT, verify=_verify_for(url))
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE * attempt
                print(f"  ! attempt {attempt}/{MAX_RETRIES} failed for {url} "
                      f"({exc}); retrying in {wait}s")
                time.sleep(wait)
    print(f"  ! giving up after {MAX_RETRIES} attempts: {url} ({last_exc})")
    return None


def fetch(session: requests.Session, url: str, dest: Path) -> FetchResult:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        # Already downloaded in a previous (possibly interrupted) run —
        # don't re-fetch it. This also quietly absorbs the http/https
        # duplicate links the site itself serves for some files.
        print(f"  (already have) {dest.name}")
        return FetchResult(url, str(dest.relative_to(ROOT)), 200, "cached", dest.stat().st_size)
    try:
        resp = _get_with_retry(session, url)
        if resp is None:
            return FetchResult(url, "", -1, "", 0)
        dest.write_bytes(resp.content)
        return FetchResult(url, str(dest.relative_to(ROOT)), resp.status_code,
                            resp.headers.get("Content-Type", ""), len(resp.content))
    finally:
        time.sleep(SLEEP_SECONDS)


def load_seed_rows() -> list[dict]:
    with SEED_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dest_for(url: str, category: str) -> Path:
    name = _safe_name_from_url(url)
    if url.lower().endswith(".pdf"):
        return PDFS_DIR / name
    if category == "news":
        return NEWS_DIR / name
    return PAGES_DIR / name


def discover_pdf_links(session: requests.Session, page_url: str) -> set[str]:
    found: set[str] = set()
    resp = _get_with_retry(session, page_url)
    time.sleep(SLEEP_SECONDS)
    if resp is None:
        return found
    if resp.status_code != 200:
        print(f"  ! {page_url} returned status {resp.status_code}")
        return found
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"])
        if "/wp-content/uploads/" in href and href.lower().endswith(".pdf"):
            found.add(href)
    return found


def discover_news_post_links(session: requests.Session) -> set[str]:
    found: set[str] = set()
    for page_num in range(1, NEWS_ARCHIVE_PAGES + 1):
        archive_url = BASE if page_num == 1 else urljoin(BASE, f"page/{page_num}/")
        resp = _get_with_retry(session, archive_url)
        time.sleep(SLEEP_SECONDS)
        if resp is None:
            break
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        page_found = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(BASE, a["href"])
            qs = parse_qs(urlparse(href).query)
            if "p" in qs:
                found.add(href)
                page_found += 1
        if page_found == 0:
            break
    return found


def main() -> None:
    print(
        "NOTE: TLS certificate verification is disabled for "
        f"{sorted(UNVERIFIED_HOSTS)} only (their cert is currently expired — "
        "confirmed against a working host in the same run). All other hosts "
        "are verified normally.\n"
    )
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    RAW.mkdir(parents=True, exist_ok=True)
    session = _session()
    results: list[FetchResult] = []

    print("== 1. Fetching hand-curated seed URLs ==")
    seed_rows = load_seed_rows()
    seed_urls = set()
    for row in seed_rows:
        url = row["url"]
        seed_urls.add(url)
        dest = dest_for(url, row["category"])
        print(f"  fetching {url}")
        results.append(fetch(session, url, dest))

    print("== 2. Crawling Publications/CDF pages for additional PDFs ==")
    extra_pdfs: set[str] = set()
    for page_url in CRAWL_FOR_LINKS:
        extra_pdfs |= discover_pdf_links(session, page_url)
    extra_pdfs -= seed_urls
    for url in sorted(extra_pdfs):
        print(f"  found new PDF: {url}")
        results.append(fetch(session, url, dest_for(url, "budget")))

    print("== 3. Walking news archive for post links ==")
    news_links = discover_news_post_links(session)
    news_links -= seed_urls
    for url in sorted(news_links):
        print(f"  fetching news post {url}")
        results.append(fetch(session, url, dest_for(url, "news")))

    print("== Writing manifest ==")
    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "local_path", "http_status", "content_type", "bytes"])
        for r in results:
            writer.writerow([r.url, r.local_path, r.status, r.content_type, r.bytes])

    ok = sum(1 for r in results if r.status == 200)
    print(f"\nDone. {ok}/{len(results)} fetched successfully. See {MANIFEST_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()