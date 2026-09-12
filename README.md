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

### → Next action

`data/raw/` now has ~20 new seed URLs that haven't been fetched yet. Re-run
the scraper (safe to re-run — anything already downloaded is skipped) to
pick them up, then start on cleaning:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/scrape.py     # downloads into data/raw/ (skips files already present)
python scripts/clean.py      # currently a stub — the next thing to build
```

`scripts/clean.py` needs to turn the raw material into the tidy
`data/processed/db-unza26-csc4792-team9-*.csv` files for submission. See the
module docstring in `scripts/clean.py` for the suggested per-source-type
approach (budget/financial PDFs, CDF skills/bursary PDFs, news posts, IDP).

## Repo layout

```
data/raw/             # untouched scraped output (HTML, PDFs) + manifest.csv
data/raw/sources_seed.csv   # hand-curated + crawl-discovered list of source URLs
data/processed/       # final db-unza26-csc4792-team9-*.csv files (not yet produced)
scripts/scrape.py     # downloads raw source material
scripts/clean.py      # raw -> tidy CSV(s) (stub, next step)
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

- [ ] **Track A — CDF + budget/financial data**: extract tables from
      budget/financial-statement PDFs and CDF skills/bursary PDFs into
      `data/processed/`.
- [ ] **Track B — IDP + council notices/resolutions**: parse the IDP for any
      tabulated priority projects; extract structured fields (date, ward,
      amount, topic) from news posts.
- [ ] **Track C — Data in Brief paper**: draft against whatever schema
      exists once Tracks A/B have produced processed CSVs.
- [ ] **Track D — Kaggle upload + dataset documentation**: once CSVs are
      stable.
- [ ] **LGEF-specific search**: no dedicated Luanshya LGEF document found
      yet — needs its own search pass (may be in the budget PDF as a line
      item rather than a standalone doc).

Keep this README updated as the source of truth for "what's claimed, what's
open" so no one duplicates work.
