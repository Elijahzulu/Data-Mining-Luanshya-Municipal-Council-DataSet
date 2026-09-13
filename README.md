# Data-Mining-Luanshya-Municipal-Council-DataSet

CSC 4792 Data in Brief project: scraping and publishing open data from the
[Luanshya Municipal Council website](https://www.luanshyacouncil.gov.zm/) —
CDF allocations/projects, budgets & financial statements, the District
Integrated Development Plan (IDP), and council notices/resolutions.

See `Contributors.md` for the team list.

## Status (as of this commit)

- **Raw data collection is done.** `data/raw/` holds 134 files fetched by
  `scripts/scrape.py`: 7 nav pages, 14 news posts, and 111 PDFs (budgets,
  financial statements, CDF lists, the IDP, by-laws, application forms,
  legal acts, etc.), all under their original filenames, indexed in
  `data/raw/manifest.csv`.
- `data/raw/sources_seed.csv` is the hand-curated + crawl-discovered seed
  list the scraper starts from. It was cross-checked against a second,
  independent crawl a teammate ran on `main` (a broader depth-crawl of the
  whole site) and topped up with ~20 documents that crawl found and this
  one had missed (legal acts, application forms, and a few recent CDF/
  performance reports) — see the entries at the bottom of the CSV.
  `main`'s own raw dump (`scrappedFiles/`) was reviewed but not merged in:
  it has no scraper script committed, uses opaque hashed filenames, and its
  categorisation columns are mostly empty — not something the cleaning step
  can build on. This branch (`data-extraction`) is the one to develop
  `scripts/clean.py` against going forward.
- **Known site issue:** `www.luanshyacouncil.gov.zm`'s TLS certificate was
  expired/invalid at scrape time. Because this only ever does read-only GETs
  of public documents, certificate verification is disabled for that one
  host specifically in `scripts/scrape.py` (see `UNVERIFIED_HOSTS`) — every
  other host is verified normally. This is a data-provenance caveat worth a
  line in the Data in Brief paper; re-enable verification for this host once
  the council fixes it.

- **Cleaning is done for most of the corpus.** `scripts/clean.py` turns
  `data/raw/` into four tidy CSVs in `data/processed/`:
  - `db-unza26-csc4792-team9-document-index.csv` — one row per raw file
    (all 128), with category, page count, and whether it had a usable text
    layer. Start here to see what's covered.
  - `db-unza26-csc4792-team9-cdf-beneficiaries.csv` — 260 rows, one per
    person, from the 4 skills/secondary-bursary lists that are both
    text-based and table-detectable (name, ward, gender, amount, list
    type). **NRC numbers, phone numbers, and dates of birth are
    deliberately excluded** — the source PDFs include them (several for
    schoolchildren on the bursary list), but they aren't needed for a
    CDF-spending analysis and meaningfully raise re-identification/contact
    risk once this is a public, searchable CSV. Don't add them back in
    without discussing it with the team first.
  - `db-unza26-csc4792-team9-budget-lines.csv` — 3,097 rows, long-format
    (code, description, amount_type, amount_kwacha) from the 4 budget/
    financial PDFs with ruled, machine-readable tables.
  - `db-unza26-csc4792-team9-news-posts.csv` — all 16 news posts, with
    published date, wards mentioned, and Kwacha amounts mentioned pulled
    out of the body text.
- **Known, real limitation — not a bug to "fix" later:** roughly half the
  PDFs (53 of 105) are CamScanner-style phone photographs with no text
  layer at all, several of them the most recent (2026) CDF beneficiary
  lists and a few financial statements/audit reports. OCR was tested
  (pytesseract) and the table structure comes out too garbled to publish
  as structured data. These are flagged `has_text_layer = False` in the
  document index rather than silently dropped, and this belongs in the
  Data in Brief paper as a genuine data-provenance limitation.
- **Not yet extracted:** 12 documents classified `cdf_project_list`
  (community-project approval lists, and the 2022–2025 consolidated CDF
  project tracker) are indexed but not yet parsed into their own CSV —
  their table layouts (merged cells, forward-filled ward columns, and one
  file pdfplumber can't even split into columns) need a purpose-built
  extractor. See the docstring in `scripts/clean.py`.
- **Known site issue:** `www.luanshyacouncil.gov.zm`'s TLS certificate was
  expired/invalid at scrape time. Because this only ever does read-only GETs
  of public documents, certificate verification is disabled for that one
  host specifically in `scripts/scrape.py` (see `UNVERIFIED_HOSTS`) — every
  other host is verified normally. This is a data-provenance caveat worth a
  line in the Data in Brief paper; re-enable verification for this host once
  the council fixes it.

### → Next action

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/scrape.py     # downloads into data/raw/ (skips files already present)
python scripts/clean.py      # raw -> tidy CSVs in data/processed/
```

Remaining real work: the `cdf_project_list` extractor described above, and
the Data in Brief paper itself (which now has real processed CSVs and
known limitations to draw on).

## Repo layout

```
data/raw/             # untouched scraped output (HTML, PDFs) + manifest.csv
data/raw/sources_seed.csv   # hand-curated + crawl-discovered list of source URLs
data/processed/       # tidy db-unza26-csc4792-team9-*.csv files for submission
scripts/scrape.py     # downloads raw source material
scripts/clean.py      # raw -> tidy CSV(s) — see its docstring for coverage/limitations
notebook.ipynb        # required deliverable notebook, built incrementally
```

## What's covered / known so far

| Category | Example source |
|---|---|
| Budget | [2025 Annual Budget](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2025/04/LUANSHYA-BUDGET-2025.pdf), [2022](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/09/LMC-Financial-Statement-2022.pdf)/[2023](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/Financial-Statements-2023-1.pdf) financial statements, [2023 Auditor's Report](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/Auditors-Report-2023.pdf), 2025 Bi-Annual Performance Report |
| CDF | [CDF page](https://www.luanshyacouncil.gov.zm/?page_id=3525) (tracker + guidelines), [2025 skills list](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/2025-SKILLS-LUANSHYA-CONSTITUENCY.pdf), [2025 bursaries list](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/2025-SECONDARY-BURSARIES-LUANSHYA-CONSTITUENCY.pdf), CDF guidelines, application/grant forms, multiple CDF project news posts |
| IDP | [District IDP 2023–2033](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2023/11/LUANSHYA-DISTRICT-INTEGRATED-DEVELOPMENT-PLAN-2023-2033.pdf) |
| Notices / resolutions / ward programs | Council news posts (by-laws, full council meeting, ward cash-for-work, DCC meeting minutes, etc.) — see `sources_seed.csv` |
| Legal / regulatory | Local Government Act, Urban and Regional Planning Act, Public Procurement Act & Regulations, Constitution of Zambia amendment |
| LGEF | Not yet located as a standalone council document — worth a dedicated search pass |

Full list with URLs: `data/raw/sources_seed.csv`.

## Division of work (fill in names as people pick up a track)

- [x] **Track A — CDF beneficiary lists + budget/financial data**: done for
      the 4 text-based, table-detectable documents of each kind (see
      Status above). Remaining: a dedicated extractor for the 12
      `cdf_project_list` documents (community projects / consolidated CDF
      tracker) — different table shape from the person-level lists.
- [ ] **Track B — IDP + council notices/resolutions**: news posts are
      structured (`db-unza26-csc4792-team9-news-posts.csv`); the IDP itself
      is still just indexed as a reference document (too large/narrative to
      fully tabulate — check whether it has a tabulated priority-projects
      section worth pulling out).
- [ ] **Track C — Data in Brief paper**: draft against whatever schema
      exists once Tracks A/B have produced processed CSVs.
- [ ] **Track D — Kaggle upload + dataset documentation**: once CSVs are
      stable.
- [ ] **LGEF-specific search**: no dedicated Luanshya LGEF document found
      yet — needs its own search pass (may be in the budget PDF as a line
      item rather than a standalone doc).

Keep this README updated as the source of truth for "what's claimed, what's
open" so no one duplicates work.
