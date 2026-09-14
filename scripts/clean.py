"""
Cleaning/transform step: turns raw scraped material in data/raw/ into the
tidy CSV(s) for submission, named per the course spec:

    data/processed/db-unza26-csc4792-team9-document-index.csv
    data/processed/db-unza26-csc4792-team9-cdf-beneficiaries.csv
    data/processed/db-unza26-csc4792-team9-budget-lines.csv
    data/processed/db-unza26-csc4792-team9-news-posts.csv

Run after scrape.py:
    python scripts/clean.py

--------------------------------------------------------------------------
WHAT THIS DOES AND DOESN'T COVER (read before trusting the output)
--------------------------------------------------------------------------
Of the ~105 PDFs scraped, roughly HALF have no real text layer — they are
phone/CamScanner photographs of paper documents (several 2026 CDF
beneficiary lists, audit reports, stakeholder-engagement minutes, etc.).
OCR was tested against a sample (pytesseract) and the table structure comes
out badly garbled — good enough to search, not good enough to publish as
structured rows. Those documents are listed in the document index with
`has_text_layer = False` and are NOT force-parsed into the other CSVs. This
is a real, material limitation of the source material and belongs in the
Data in Brief paper as such, not something to quietly work around.

Of the PDFs that DO have a text layer, table *structure* still varies a lot
(some use ruled tables pdfplumber can detect directly, some are pure
whitespace-aligned narrative text with no detectable table at all — e.g.
the 2018-2021 and 2024 Annual Detailed Budgets). Only tables pdfplumber can
actually detect are parsed into cdf-beneficiaries.csv / budget-lines.csv;
everything else still gets a full-text entry in the document index so it's
searchable, but isn't force-fit into a row/column shape it doesn't have.

NOT YET DONE (left for a follow-up pass, not silently dropped): documents
classified as `cdf_project_list` (community-project approval lists, and the
2022-2025 consolidated CDF project tracker) are indexed but not extracted
into their own CSV. Their table shapes are meaningfully different from the
person-level bursary/skills lists — multi-line merged cells, ward/
constituency values that need forward-filling down blank rows, and (for the
consolidated tracker) a layout pdfplumber can't even split into columns —
so they need a purpose-built extractor rather than a rushed reuse of
extract_person_records. Filter document-index.csv on
category == "cdf_project_list" to see what's waiting.

PRIVACY: the CDF skills/bursary/empowerment-grant lists include, in the
source PDFs, national ID numbers (NRC), phone numbers, and dates of birth
for named individuals (many of them schoolchildren, for the bursary
lists). Per an explicit decision on this dataset, cdf-beneficiaries.csv
keeps name/ward/programme/amount (useful for the CDF-spending analysis)
and DROPS NRC numbers, phone numbers, and date of birth — those aren't
needed for that analysis and meaningfully increase re-identification/
contact risk once this is a public, searchable CSV rather than a PDF
buried on a low-traffic government site.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PDFS_DIR = RAW / "pdfs"
PAGES_DIR = RAW / "pages"
NEWS_DIR = RAW / "news"
MANIFEST_CSV = RAW / "manifest.csv"
SEED_CSV = RAW / "sources_seed.csv"
PROCESSED = ROOT / "data" / "processed"

# Privacy (see module docstring): extract_person_records() below reads an
# ALLOWLIST of columns (name/ward/gender/amount/constituency) into the
# output, never a denylist of columns to drop — NRC numbers, phone numbers
# and dates of birth are excluded simply because nothing ever asks for
# them, which is safer than trying to enumerate every way a PDF might spell
# those header names.

# Filename keyword -> list_type, for the person-level CDF beneficiary lists.
PERSON_LIST_TYPE_RULES = [
    (("SKILL",), "skills_development"),
    (("SECONDARY", "BOARDING", "BURSAR"), "secondary_bursary"),
    (("EMPOWERMENT", "GRANT"), "empowerment_grant"),
    (("LOAN",), "loan"),
]

WARD_HEADER_KEYWORDS = ("WARD",)
NAME_HEADER_KEYWORDS = ("NAME OF STUDENT", "NAME OF PUPIL",
                         "NAME OF BENEFICIARY", "NAME OF APPLICANT")
GENDER_HEADER_KEYWORDS = ("GENDER", "SEX")
AMOUNT_HEADER_KEYWORDS = ("FEES / ANNUM", "FEES ANNUM", "FEES PER ANNUM",
                          "ANNUAL FEES", "GRANT AMOUNT", "LOAN AMOUNT",
                          "AMOUNT", "TOTAL")
CONSTITUENCY_HEADER_KEYWORDS = ("CONSTITUENCY",)


def _norm_header(cell) -> str:
    """Collapse a (possibly multi-line) table header cell to one
    upper-case, single-spaced string for keyword matching."""
    if cell is None:
        return ""
    return re.sub(r"\s+", " ", str(cell)).strip().upper()


def _find_col(headers: list[str], keywords: tuple[str, ...]) -> int | None:
    """Substring-match a header against keywords, tolerant of PDF text
    extraction sometimes breaking a table header across lines mid-word
    (e.g. "GENDE\nR (F/M)") — compare with all whitespace stripped too."""
    headers_nospace = [h.replace(" ", "") for h in headers]
    for kw in keywords:
        kw_nospace = kw.replace(" ", "")
        for i, (h, h_ns) in enumerate(zip(headers, headers_nospace)):
            if kw in h or kw_nospace in h_ns:
                return i
    return None


def _parse_amount(raw) -> float | None:
    if raw is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(raw))
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _year_from_name(text: str) -> int | None:
    m = re.search(r"\b(20[1-3][0-9])\b", text)
    return int(m.group(1)) if m else None


def _constituency_from_name(text: str) -> str | None:
    t = text.upper()
    if "ROAN" in t:
        return "Roan"
    if "LUANSHYA" in t:
        return "Luanshya"
    return None


# --------------------------------------------------------------------------
# 1. Document index — one row per raw file, regardless of whether it could
#    be further parsed. This is the master inventory the other CSVs are
#    drawn from.
# --------------------------------------------------------------------------

@dataclass
class DocRecord:
    local_path: str
    url: str
    doc_type: str          # page | news | pdf
    category: str
    title: str
    http_status: str
    bytes: str
    page_count: int | None = None
    has_text_layer: bool | None = None
    table_detected: bool | None = None
    notes: str = ""


def load_manifest() -> pd.DataFrame:
    if not MANIFEST_CSV.exists():
        raise SystemExit(f"{MANIFEST_CSV} not found — run scripts/scrape.py first.")
    df = pd.read_csv(MANIFEST_CSV)
    # scrape.py writes Windows-style backslash paths when run on Windows;
    # normalise so this script works regardless of which OS produced them.
    df["local_path"] = df["local_path"].str.replace("\\", "/", regex=False)
    # The council links the same file over both http:// and https://, and
    # the seed list + the Publications/CDF crawl sometimes both find it —
    # scrape.py correctly saves it once, but manifest.csv still gets one
    # row per URL that pointed at it. Keep one row per actual file, and
    # prefer https when both are present so seed_lookup (below) still
    # matches it.
    df = df.sort_values("url", ascending=False).drop_duplicates("local_path", keep="first")
    return df


def load_seed_lookup() -> dict[str, tuple[str, str]]:
    """url -> (category, title) from the hand-curated seed list. Only
    covers the ~50 originally-seeded URLs; PDFs auto-discovered by the
    Publications/CDF crawl aren't in here and get category inferred from
    their filename instead (see classify_pdf_category)."""
    if not SEED_CSV.exists():
        return {}
    lookup = {}
    with SEED_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lookup[row["url"]] = (row["category"], row["title"])
    return lookup


def classify_pdf_category(filename: str) -> str:
    name = filename.upper()
    # "BURS" (not "BURSAR") because the council's own filenames sometimes
    # misspell it "bursuries" instead of "bursaries" (e.g. the Roan
    # secondary-school list) — a shorter stem survives that typo.
    if any(k in name for k in ("SKILL", "BURS", "EMPOWERMENT", "GRANT", "LOAN")):
        return "cdf_beneficiary_list"
    if any(k in name for k in ("COMMUNITY-PROJECT", "COMMUNITY PROJECTS", "CONSOLIDATED")):
        return "cdf_project_list"
    if "INTEGRATED-DEVELOPMENT-PLAN" in name:
        return "idp"
    if any(k in name for k in ("BUDGET", "FINANCIAL-STATEMENT", "FINANCIAL STATEMENT",
                                "AUDIT", "BI-ANNUAL")):
        return "budget_financial"
    if any(k in name for k in ("ACT-NO", "ACT NO", "-ACT-", "REGULATIONS", "LICENSING")):
        return "legal_regulatory"
    if any(k in name for k in ("NOTICE", "MINUTES", "AGENDA", "MEETING")):
        return "notice_minutes"
    if any(k in name for k in ("APPLICATION-FORM", "APPLICATION FORM", "ADVERT", "FORM")):
        return "application_form"
    return "misc"


def pdf_stats(path: Path) -> tuple[int | None, bool | None, bool | None]:
    """Returns (page_count, has_text_layer, table_detected)."""
    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            first_text = (pdf.pages[0].extract_text() or "").strip()
            has_text = len(first_text) >= 20
            table_found = False
            if has_text:
                for p in pdf.pages[: min(page_count, 5)]:
                    if p.extract_tables():
                        table_found = True
                        break
            return page_count, has_text, table_found
    except Exception:
        return None, None, None


def build_document_index() -> pd.DataFrame:
    manifest = load_manifest()
    seed_lookup = load_seed_lookup()
    records: list[DocRecord] = []

    for _, row in manifest.iterrows():
        local_path = str(row["local_path"])
        url = str(row["url"])
        full_path = ROOT / local_path
        seed_category, seed_title = seed_lookup.get(url, ("", ""))

        if "/pages/" in local_path:
            doc_type = "page"
            category = seed_category or "nav_page"
            title = seed_title or Path(local_path).stem
            rec = DocRecord(local_path, url, doc_type, category, title,
                             str(row["http_status"]), str(row["bytes"]))
        elif "/news/" in local_path:
            doc_type = "news"
            category = seed_category or "news"
            title = seed_title or Path(local_path).stem
            rec = DocRecord(local_path, url, doc_type, category, title,
                             str(row["http_status"]), str(row["bytes"]))
        else:
            doc_type = "pdf"
            filename = Path(local_path).name
            # Always use the filename-based classifier for PDFs, even when
            # the URL is also in sources_seed.csv — the seed list's category
            # column uses a coarser, inconsistent vocabulary (e.g. "budget",
            # "cdf") that doesn't line up with what extract_person_records /
            # extract_budget_lines filter on below, which silently excludes
            # a document if it happens to carry the seed's category instead.
            category = classify_pdf_category(filename)
            title = seed_title or filename
            page_count, has_text, table_found = (None, None, None)
            if full_path.exists():
                page_count, has_text, table_found = pdf_stats(full_path)
            notes = "" if full_path.exists() else "file not present on disk"
            rec = DocRecord(local_path, url, doc_type, category, title,
                             str(row["http_status"]), str(row["bytes"]),
                             page_count, has_text, table_found, notes)
        records.append(rec)

    return pd.DataFrame([r.__dict__ for r in records])


# --------------------------------------------------------------------------
# 2. CDF beneficiary lists (person-level: skills / secondary bursaries /
#    empowerment grants / loans). Only attempted on PDFs pdfplumber can
#    already see as having both a text layer AND a detectable table, whose
#    header row names a person-level list (NAME OF STUDENT/PUPIL/etc).
# --------------------------------------------------------------------------

def list_type_for(filename: str) -> str | None:
    name = filename.upper()
    for keywords, list_type in PERSON_LIST_TYPE_RULES:
        if any(k in name for k in keywords):
            return list_type
    return None


def extract_person_records(doc_index: pd.DataFrame) -> pd.DataFrame:
    rows = []
    candidates = doc_index[(doc_index.doc_type == "pdf")
                            & (doc_index.category == "cdf_beneficiary_list")
                            & (doc_index.has_text_layer == True)  # noqa: E712
                            & (doc_index.table_detected == True)]  # noqa: E712

    for _, doc in candidates.iterrows():
        filename = Path(doc.local_path).name
        list_type = list_type_for(filename) or "other_cdf_list"
        constituency = _constituency_from_name(filename) or "Luanshya"
        year = _year_from_name(filename)
        full_path = ROOT / doc.local_path

        header = None
        col_map = None
        n_rows_for_doc = 0
        with pdfplumber.open(full_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table:
                        continue
                    for raw_row in table:
                        norm = [_norm_header(c) for c in raw_row]
                        looks_like_header = _find_col(norm, NAME_HEADER_KEYWORDS) is not None
                        if looks_like_header:
                            header = norm
                            col_map = {
                                "name": _find_col(header, NAME_HEADER_KEYWORDS),
                                "ward": _find_col(header, WARD_HEADER_KEYWORDS),
                                "gender": _find_col(header, GENDER_HEADER_KEYWORDS),
                                "amount": _find_col(header, AMOUNT_HEADER_KEYWORDS),
                                "constituency": _find_col(header, CONSTITUENCY_HEADER_KEYWORDS),
                            }
                            continue
                        if col_map is None or col_map["name"] is None:
                            continue
                        name_val = raw_row[col_map["name"]] if col_map["name"] < len(raw_row) else None
                        name_val = re.sub(r"\s+", " ", str(name_val or "")).strip()
                        if not name_val or name_val.upper() in ("NONE", ""):
                            continue

                        def cell(key):
                            idx = col_map.get(key)
                            if idx is None or idx >= len(raw_row):
                                return None
                            v = raw_row[idx]
                            return re.sub(r"\s+", " ", str(v)).strip() if v else None

                        rows.append({
                            "source_document": filename,
                            "list_type": list_type,
                            "constituency": cell("constituency") or constituency,
                            "ward": cell("ward"),
                            "beneficiary_name": name_val,
                            "gender": cell("gender"),
                            "amount_kwacha": _parse_amount(cell("amount")),
                            "year": year,
                        })
                        n_rows_for_doc += 1
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 3. Budget line items — long format (source_document, code, description,
#    amount_type [the column header, e.g. "APPROVED BUDGET 2025"],
#    amount_kwacha). Only attempted where pdfplumber detects an actual
#    ruled table with a CODE/DESCRIPTION-shaped header.
# --------------------------------------------------------------------------

BUDGET_CODE_HEADER_KEYWORDS = ("CODE",)
BUDGET_DESC_HEADER_KEYWORDS = ("DESCRIPTION", "DETAILS")


def extract_budget_lines(doc_index: pd.DataFrame) -> pd.DataFrame:
    rows = []
    candidates = doc_index[(doc_index.doc_type == "pdf")
                            & (doc_index.category == "budget_financial")
                            & (doc_index.has_text_layer == True)  # noqa: E712
                            & (doc_index.table_detected == True)]  # noqa: E712

    for _, doc in candidates.iterrows():
        filename = Path(doc.local_path).name
        year = _year_from_name(filename)
        full_path = ROOT / doc.local_path
        header = None
        code_i = desc_i = None
        amount_cols: dict[int, str] = {}

        with pdfplumber.open(full_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table:
                        continue
                    for raw_row in table:
                        norm = [_norm_header(c) for c in raw_row]
                        has_code = _find_col(norm, BUDGET_CODE_HEADER_KEYWORDS) is not None
                        has_desc = _find_col(norm, BUDGET_DESC_HEADER_KEYWORDS) is not None
                        if has_code and has_desc:
                            header = norm
                            code_i = _find_col(header, BUDGET_CODE_HEADER_KEYWORDS)
                            desc_i = _find_col(header, BUDGET_DESC_HEADER_KEYWORDS)
                            amount_cols = {
                                i: h for i, h in enumerate(header)
                                if i not in (code_i, desc_i) and h
                            }
                            continue
                        if header is None or desc_i is None:
                            continue
                        if desc_i >= len(raw_row):
                            continue
                        desc_val = re.sub(r"\s+", " ", str(raw_row[desc_i] or "")).strip()
                        if not desc_val:
                            continue
                        code_val = None
                        if code_i is not None and code_i < len(raw_row) and raw_row[code_i]:
                            code_val = re.sub(r"\s+", " ", str(raw_row[code_i])).strip()
                        for i, amount_label in amount_cols.items():
                            if i >= len(raw_row):
                                continue
                            amount = _parse_amount(raw_row[i])
                            if amount is None:
                                continue
                            rows.append({
                                "source_document": filename,
                                "year": year,
                                "code": code_val,
                                "description": desc_val,
                                "amount_type": amount_label,
                                "amount_kwacha": amount,
                            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 4. News posts — structured fields out of the WordPress HTML posts.
# --------------------------------------------------------------------------

# Require an actual digit right after the K (with at most one space) — a
# bare "[\d,]+" also accepts a lone comma, which matched things like
# "Clerk," or "Mark," as fake Kwacha amounts. \b before K keeps it from
# matching the "k" inside an ordinary word (e.g. the "k" in "Bank,").
AMOUNT_RE = re.compile(r"\bK\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion))?\b", re.IGNORECASE)


def extract_news_posts(doc_index: pd.DataFrame, wards: set[str]) -> pd.DataFrame:
    rows = []
    candidates = doc_index[doc_index.doc_type == "news"]
    ward_patterns = sorted((w for w in wards if w), key=len, reverse=True)

    for _, doc in candidates.iterrows():
        full_path = ROOT / doc.local_path
        if not full_path.exists():
            continue
        html = full_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else doc.title
        title = re.sub(r"\s*[–-]\s*Luanshya Municipal Council.*$", "", title).strip()

        article = soup.find("article") or soup.find("div", class_="entry-content")
        body_text = article.get_text(" ", strip=True) if article else soup.get_text(" ", strip=True)

        # WordPress posts carry a proper <time datetime="..."> tag — use
        # that instead of regexing the body for a spelled-out date (these
        # posts don't put the date in the body text at all).
        time_tag = soup.find("time")
        published_date = None
        if time_tag and time_tag.get("datetime"):
            published_date = time_tag["datetime"][:10]  # YYYY-MM-DD

        wards_mentioned = sorted({w for w in ward_patterns if w and w.upper() in body_text.upper()})
        amounts = sorted({m.rstrip(",.; ") for m in AMOUNT_RE.findall(body_text)})

        rows.append({
            "source_document": Path(doc.local_path).name,
            "url": doc.url,
            "title": title,
            "published_date": published_date,
            "wards_mentioned": "; ".join(wards_mentioned) if wards_mentioned else None,
            "kwacha_amounts_mentioned": "; ".join(amounts) if amounts else None,
            "word_count": len(body_text.split()),
            "body_text": body_text,
        })
    return pd.DataFrame(rows)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_CSV.exists():
        print(
            "No data/raw/manifest.csv found yet — run scripts/scrape.py "
            "first (from a machine with real internet access; see README.md)."
        )
        return

    print("== Building document index ==")
    doc_index = build_document_index()
    doc_index.to_csv(PROCESSED / "db-unza26-csc4792-team9-document-index.csv", index=False, sep="|")
    n_pdf = (doc_index.doc_type == "pdf").sum()
    n_no_text = ((doc_index.doc_type == "pdf") & (doc_index.has_text_layer == False)).sum()  # noqa: E712
    print(f"  {len(doc_index)} documents indexed ({n_pdf} PDFs, {n_no_text} with no usable text layer)")

    print("== Extracting CDF beneficiary/project person-level records ==")
    people = extract_person_records(doc_index)
    people.to_csv(PROCESSED / "db-unza26-csc4792-team9-cdf-beneficiaries.csv", index=False, sep="|")
    print(f"  {len(people)} beneficiary rows from "
          f"{people.source_document.nunique() if not people.empty else 0} documents")

    print("== Extracting budget line items ==")
    budget = extract_budget_lines(doc_index)
    budget.to_csv(PROCESSED / "db-unza26-csc4792-team9-budget-lines.csv", index=False, sep="|")
    print(f"  {len(budget)} budget line rows from "
          f"{budget.source_document.nunique() if not budget.empty else 0} documents")

    print("== Extracting news posts ==")
    wards = set(people["ward"].dropna().unique()) if not people.empty else set()
    news = extract_news_posts(doc_index, wards)
    news.to_csv(PROCESSED / "db-unza26-csc4792-team9-news-posts.csv", index=False, sep="|")
    print(f"  {len(news)} news posts")

    n_project_list = (doc_index.category == "cdf_project_list").sum()
    print(f"\nDone. Output in {PROCESSED.relative_to(ROOT)}/")
    print(f"NOT YET EXTRACTED: {n_project_list} 'cdf_project_list' documents "
          "(community-project lists / the consolidated CDF tracker) are "
          "indexed but need their own extractor — see the module docstring.")
    print("See the module docstring for what else is and isn't covered "
          "(half the PDFs are scanned images with no usable text layer).")


if __name__ == "__main__":
    main()
