"""Cross-validate this branch's document coverage against an independent crawl.

The comparison crawl (data/raw/blessing_independent_crawl/) is a separate
breadth-first, keyword-categorised crawler, built and run independently of
this branch's scripts/scrape.py (a curated seed list + crawl-discovery).
Neither crawl was used to build the other; this script only compares their
two independently-produced URL lists after the fact.

Why this matters for the Data in Brief paper: a single crawl's coverage claim
("we found all the CDF/budget/IDP documents on the site") is not verifiable on
its own. Two independently-written crawlers substantially agreeing on what
exists is real evidence of completeness; where they disagree tells you exactly
what to go check by hand. That is the only thing this script establishes — it
is a coverage check, not a data source. The actual dataset is still built from
data/raw/ (scripts/scrape.py) and cleaned by scripts/clean.py.

Output: data/processed/db-unza26-csc4792-team9-coverage-validation.csv
  columns: url | in_team_pipeline | in_blessing_crawl | blessing_category
"""
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BLESSING_DIR = RAW / "blessing_independent_crawl"
PROCESSED = ROOT / "data" / "processed"


def normalize_url(url: str) -> str:
    """Make URLs from the two independently-written crawlers comparable:
    force https, drop a trailing slash, and drop any fragment. Query strings
    (e.g. ?page_id=959) are kept — they're how this WordPress site
    distinguishes pages."""
    if not isinstance(url, str) or not url.strip():
        return ""
    parsed = urlparse(url.strip())
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def load_team_urls() -> set[str]:
    """Every URL this branch actually fetched, per data/raw/manifest.csv —
    the ground truth for 'what's in the pipeline', independent of which seed
    list (curated, crawl-discovered, or topped-up from the independent crawl's URL list)
    a given entry originally came from."""
    manifest = pd.read_csv(RAW / "manifest.csv")
    return {normalize_url(u) for u in manifest["url"].dropna()} - {""}


def load_blessing_urls() -> pd.DataFrame:
    """The independent crawl's crawled pages + linked documents, with its
    keyword-based category tags, as one url -> category table."""
    pages = pd.read_csv(BLESSING_DIR / "db-unza26-csc4792-luanshya_council_crawled_pages.csv", sep="|")
    docs = pd.read_csv(BLESSING_DIR / "db-unza26-csc4792-luanshya_council_documents.csv", sep="|")

    page_rows = pages[["url", "categories"]].rename(columns={"categories": "category"})
    doc_rows = docs[["pdf_url", "category"]].rename(columns={"pdf_url": "url"})

    combined = pd.concat([page_rows, doc_rows], ignore_index=True)
    combined["url_norm"] = combined["url"].apply(normalize_url)
    combined = combined[combined["url_norm"] != ""]
    # A URL can appear more than once (e.g. one PDF linked from several pages);
    # keep first-seen category, it's not worth reconciling duplicates for a
    # coverage check.
    combined = combined.drop_duplicates(subset="url_norm", keep="first")
    return combined.set_index("url_norm")["category"]


def main() -> None:
    team_urls = load_team_urls()
    blessing_categories = load_blessing_urls()
    blessing_urls = set(blessing_categories.index)

    all_urls = sorted(team_urls | blessing_urls)
    report = pd.DataFrame({
        "url": all_urls,
        "in_team_pipeline": [u in team_urls for u in all_urls],
        "in_blessing_crawl": [u in blessing_urls for u in all_urls],
    })
    report["blessing_category"] = report["url"].map(blessing_categories).fillna("")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED / "db-unza26-csc4792-team9-coverage-validation.csv"
    report.to_csv(out_path, index=False, sep="|")

    both = ((report["in_team_pipeline"]) & (report["in_blessing_crawl"])).sum()
    only_team = ((report["in_team_pipeline"]) & (~report["in_blessing_crawl"])).sum()
    only_blessing = ((~report["in_team_pipeline"]) & (report["in_blessing_crawl"])).sum()

    print(f"Team pipeline URLs:        {len(team_urls)}")
    print(f"Independent crawl URLs:    {len(blessing_urls)}")
    print(f"Found by both crawls:      {both}")
    print(f"Only in team pipeline:     {only_team}  (not visited/linked by the independent crawl)")
    print(f"Only in independent crawl: {only_blessing}  (candidates worth checking by hand)")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
