# Independent discovery crawl — Blessing Yabe

These two files are the unmodified output of a second, independently written
crawler (breadth-first, keyword-categorised, `MAX_DEPTH=4` / `MAX_PAGES=300`)
that Blessing Yabe ran against the same council website, separately from the
seed+depth crawl this branch's `scripts/scrape.py` uses.

They were originally committed to `main` in `scrappedFiles/data/` (commit
`da308ba`, "Added raw data scrapped from site") alongside 128 opaque,
hash-named raw HTML/PDF files. Those raw files aren't reproduced here — they
have no scraper script attached, no usable categorisation, and are keyed by
`md5(url)` filenames with no manifest tying them back to a source — so they
can't be verified or built on. These two CSVs are different: they list the
**actual URLs** her crawler visited and categorised, which is exactly the
input needed to check one crawl's coverage against the other.

- `db-unza26-csc4792-luanshya_council_crawled_pages.csv` — 68 HTML pages
  crawled, with title, crawl depth, HTTP status, and her keyword-based
  category tags.
- `db-unza26-csc4792-luanshya_council_documents.csv` — 132 linked PDF/document
  URLs, with the page that linked to each one and its inherited category.

`scripts/validate_coverage.py` uses these to cross-check this branch's
`data/raw/manifest.csv` against an independently-built list, rather than
trusting a single crawl's coverage claim — see that script and the
"Coverage cross-validation" section of `notebook.ipynb` for the result.
