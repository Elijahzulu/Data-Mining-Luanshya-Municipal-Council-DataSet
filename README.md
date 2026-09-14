# Data-Mining-Luanshya-Municipal-Council-DataSet

CSC 4792 Data Mining and Warehousing project: scraping and publishing structured
data from the [Luanshya Municipal Council website](https://www.luanshyacouncil.gov.zm/) —
CDF beneficiaries/projects, budgets & financial records, the District Integrated
Development Plan (IDP), council news, notices, and supporting documents.

See `Contributors.md` for the team list.

## Status (as of this commit)

* **Raw data collection is complete.** `data/raw/` contains the source material
  collected by `scripts/scrape.py`, including HTML pages, news posts, and PDF
  documents covering budgets, financial statements, CDF records, the IDP,
  notices, legal/regulatory documents, application forms, and other council
  publications. The collected material is indexed in
  `data/raw/manifest.csv` and the processed document inventory.

* `data/raw/sources_seed.csv` is the hand-curated + crawl-discovered seed list
  used for source acquisition. It was cross-checked against a second,
  independently written crawl in `data/raw/blessing_independent_crawl/`.
  The independent crawl was used to compare URL coverage and identify
  differences in the available site structure.

* **Known site issue:** `www.luanshyacouncil.gov.zm` had an expired/invalid
  TLS certificate at scrape time. Because the scraper performs read-only GET
  requests for public documents, certificate verification is disabled for that
  host specifically in `scripts/scrape.py` through `UNVERIFIED_HOSTS`. Other
  hosts continue to use normal certificate verification. This is retained as a
  data-provenance caveat.

* **Data cleaning and extraction are complete.** `scripts/clean.py` generates
  seven processed CSV files in `data/processed/`, containing **3,805 records**
  in total:

  * `db-unza26-csc4792-team9-budget-lines.csv` — 3,097 rows, 6 variables,
    containing budget and financial line items with codes, descriptions,
    amount types, years, and normalized Kwacha amounts.
  * `db-unza26-csc4792-team9-cdf-beneficiaries.csv` — 260 rows, 8 variables,
    containing CDF beneficiary records with constituency, ward, beneficiary
    name, gender where reported, list type, year, and amount.
  * `db-unza26-csc4792-team9-cdf-projects.csv` — 60 rows, 7 variables,
    containing CDF community-project records with ward, project name,
    allocated amount, status, year, and source information.
  * `db-unza26-csc4792-team9-coverage-validation.csv` — 208 rows, 4 variables,
    containing URL-level comparison results between the project crawl and the
    independent crawl.
  * `db-unza26-csc4792-team9-document-index.csv` — 151 rows, 11 variables,
    containing the indexed source documents and their metadata, including
    category, page count, text-layer availability, and table-detection status.
  * `db-unza26-csc4792-team9-idp-priority-projects.csv` — 13 rows, 2 variables,
    containing priority-project rows extracted from the Luanshya District
    Integrated Development Plan.
  * `db-unza26-csc4792-team9-news-posts.csv` — 16 rows, 8 variables,
    containing structured records for council news posts, including title,
    publication date, wards mentioned, Kwacha amounts mentioned, word count,
    and body text.

* **Coverage was cross-validated against an independent crawl.**
  `scripts/validate_coverage.py` compares the project's URL inventory against
  the independent crawl stored in
  `data/raw/blessing_independent_crawl/`. The two crawls share **136 URLs**.
  Differences include navigation and archive URLs, duplicate permalink forms,
  additional news-post URLs, later-published documents, and other crawl
  behaviour. The detailed comparison is stored in
  `db-unza26-csc4792-team9-coverage-validation.csv`.

* **Known data limitation:** 62 of the 151 indexed source documents are
  scanned documents without usable digital text layers. OCR was tested using
  `pytesseract`, with scanned PDFs rendered using `pdf2image`, but some outputs
  were too unreliable for conversion into structured records. These documents
  remain represented in the document index and are flagged through their
  metadata rather than being converted into unreliable structured values.

* **CDF project extraction is complete.** The project-list documents required
  custom handling because of varying table layouts, merged cells, and ward
  values carried across rows. The resulting structured records are available
  in `db-unza26-csc4792-team9-cdf-projects.csv`.

* **Privacy handling is applied to beneficiary records.** National Registration
  Card numbers, telephone numbers, and dates of birth were excluded from the
  processed beneficiary dataset. The retained fields are limited to those
  required for the project, including constituency, ward, beneficiary name,
  gender where reported, year, list type, and amount.

### → Project execution

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/scrape.py
python scripts/clean.py
python scripts/validate_coverage.py
```

The three scripts correspond to source acquisition, data cleaning/extraction,
and URL-level coverage validation respectively.

## Repo layout

```text
data/raw/                         # scraped HTML, PDFs, manifests and source lists
data/raw/sources_seed.csv        # hand-curated + crawl-discovered source URLs
data/raw/blessing_independent_crawl/
                                  # independent crawl used for coverage validation
data/processed/                  # final db-unza26-csc4792-team9-*.csv files
scripts/scrape.py                # downloads and records raw source material
scripts/clean.py                 # raw source material -> processed CSV files
scripts/validate_coverage.py     # compares coverage against independent crawl
notebook.ipynb                   # project computational notebook
requirements.txt                 # Python dependencies
Contributors.md                  # project contributors
README.md                        # project documentation
```

## What's covered / known so far

| Category                     | Example source                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Budget                       | [2025 Annual Budget](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2025/04/LUANSHYA-BUDGET-2025.pdf), [2022 Financial Statements](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/09/LMC-Financial-Statement-2022.pdf), [2023 Financial Statements](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/Financial-Statements-2023-1.pdf), [2023 Auditor's Report](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/Auditors-Report-2023.pdf), and other budget/financial publications |
| CDF                          | [CDF page](https://www.luanshyacouncil.gov.zm/?page_id=3525), [2025 skills list](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/2025-SKILLS-LUANSHYA-CONSTITUENCY.pdf), [2025 bursaries list](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2024/12/2025-SECONDARY-BURSARIES-LUANSHYA-CONSTITUENCY.pdf), CDF project lists, beneficiary lists, guidelines, application/grant forms, and CDF-related news                                                                                                 |
| IDP                          | [Luanshya District Integrated Development Plan 2023–2033](https://www.luanshyacouncil.gov.zm/wp-content/uploads/2023/11/LUANSHYA-DISTRICT-INTEGRATED-DEVELOPMENT-PLAN-2023-2033.pdf)                                                                                                                                                                                                                                                                                                                                            |
| News / notices / resolutions | Council news posts covering meetings, ward programmes, notices, by-laws, CDF activities, and other municipal publications                                                                                                                                                                                                                                                                                                                                                                                                       |
| Legal / regulatory           | Local Government Act, Urban and Regional Planning Act, Public Procurement Act and Regulations, Constitution of Zambia amendment, and related regulatory documents                                                                                                                                                                                                                                                                                                                                                               |
| LGEF                         | Present as a budget line item — "Local Government Equalisation Fund", code `004` — within the budget data rather than as a standalone dataset                                                                                                                                                                                                                                                                                                                                                                                   |

Full source inventory: `data/raw/sources_seed.csv`.

## Processed datasets

All processed datasets are stored in `data/processed/` using UTF-8,
pipe-delimited (`|`) CSV format.

| File                                                | Records | Variables |
| --------------------------------------------------- | ------: | --------: |
| `db-unza26-csc4792-team9-budget-lines.csv`          |   3,097 |         6 |
| `db-unza26-csc4792-team9-cdf-beneficiaries.csv`     |     260 |         8 |
| `db-unza26-csc4792-team9-cdf-projects.csv`          |      60 |         7 |
| `db-unza26-csc4792-team9-coverage-validation.csv`   |     208 |         4 |
| `db-unza26-csc4792-team9-document-index.csv`        |     151 |        11 |
| `db-unza26-csc4792-team9-idp-priority-projects.csv` |      13 |         2 |
| `db-unza26-csc4792-team9-news-posts.csv`            |      16 |         8 |

To read the processed files with pandas:

```python
import pandas as pd

df = pd.read_csv(
    "data/processed/db-unza26-csc4792-team9-budget-lines.csv",
    sep="|"
)
```

## Data handling and privacy

The processed beneficiary dataset intentionally excludes direct personal
identifiers present in some source documents, including:

* National Registration Card numbers
* telephone numbers
* dates of birth

The retained beneficiary fields include constituency, ward, beneficiary name,
gender where reported, list type, year, and amount.

Scanned documents that could not be reliably converted through OCR remain
represented in the document index rather than being populated with uncertain
values.

## Data limitations

The main limitation is the availability and structure of the original council
documents. Some source PDFs are scanned images without machine-readable text,
and OCR results for some documents were not sufficiently reliable for
structured extraction. PDF layouts also vary between publications, requiring
different extraction and cleaning procedures.

The news dataset represents the council news posts that were accessible during
the collection period. Likewise, the coverage-validation results depend on the
URLs and site structure available to the crawlers at collection time.

These limitations are retained in the project documentation and should be
considered when using the processed datasets.

## Project deliverables

The project deliverables include:

* Raw source collection in `data/raw/`
* Source and document inventories
* Seven processed datasets in `data/processed/`
* Coverage validation against an independent crawl
* Data-processing scripts in `scripts/`
* Computational notebook in `notebook.ipynb`
* Project documentation in `README.md`
* Contributors list in `Contributors.md`
* Dataset publication/documentation on Kaggle

## Division of work

* [x] **Track A — CDF beneficiary lists + budget/financial data:** completed.
  Structured beneficiary, budget, financial, and CDF project datasets have
  been generated in `data/processed/`.

* [x] **Track B — IDP + council notices/resolutions:** completed.
  Council news posts were structured into
  `db-unza26-csc4792-team9-news-posts.csv`, while priority-project records
  were extracted from the IDP into
  `db-unza26-csc4792-team9-idp-priority-projects.csv`.

* [x] **Track C — Data article:** completed.
  The project data article was prepared using the processed datasets,
  documented methods, limitations, and ethical considerations.

* [x] **Track D — Dataset publication + documentation:** completed.
  The processed datasets and supporting documentation were prepared for
  publication, including the Kaggle dataset.

* [x] **LGEF-specific search:** resolved.
  The Local Government Equalisation Fund was identified as a real budget
  line item (`004`) within the council budget documents and is already
  represented in `db-unza26-csc4792-team9-budget-lines.csv`.

Keep this README updated as the source of truth for the project's source
coverage, processed datasets, scripts, and remaining documentation changes.
