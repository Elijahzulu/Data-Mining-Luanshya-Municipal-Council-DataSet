"""
Cleaning/transform step: turns raw scraped material in data/raw/ into the
final tidy CSV(s) for submission, named per the course spec, e.g.:

    data/processed/db-unza26-csc4792-team9-cdf-projects.csv
    data/processed/db-unza26-csc4792-team9-budget-lines.csv

This is a stub — fill in the parsing logic once scripts/scrape.py has
actually pulled real files into data/raw/pdfs/, data/raw/pages/, and
data/raw/news/ (it hasn't yet as of this commit; see README.md).

Suggested approach per source type:
  - Budget / financial statement PDFs -> pdfplumber table extraction into a
    long-format (year, department/fund, line_item, amount_kwacha) table.
  - CDF skills/bursary list PDFs -> pdfplumber -> one row per beneficiary
    or project (name, ward, amount, category).
  - News posts (HTML) -> BeautifulSoup text extraction -> one row per post
    with date, title, body_text, and any Kwacha amounts / ward names
    regex-extracted as structured columns where possible.
  - IDP PDF -> likely just kept as a reference document (too large/narrative
    to fully tabulate); extract the priority-project tables if present.

Run after scrape.py:
    python scripts/clean.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    manifest = RAW / "manifest.csv"
    if not manifest.exists():
        print(
            "No data/raw/manifest.csv found yet — run scripts/scrape.py "
            "first (from a machine with real internet access; see README.md)."
        )
        return
    # TODO: implement per-source parsing described in the module docstring
    # once real raw files exist to develop against.
    print("TODO: implement cleaning once raw files are available.")


if __name__ == "__main__":
    main()
