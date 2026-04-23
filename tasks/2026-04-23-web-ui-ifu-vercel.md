# Task: Web UI for IFU generation on Vercel

Created: 2026-04-23

## Problem

The IFU generator scripts currently run locally via CLI. There is no way
for a non-developer user to upload their Yuh and/or Wise CSVs and get the
output IFU files without setting up Python locally.

## Proposed solution

Host a minimal web app on Vercel with:
- A single HTML form where the user selects a year and uploads a Yuh CSV
  and/or a Wise CSV (both optional independently).
- A Vercel Python serverless function (`api/process.py`) that receives the
  multipart form, runs the processing logic in memory (no disk writes), and
  returns a ZIP of all output CSVs plus the unified README.md.
- The FX cache is stored as a committed JSON file (`src/fx_cache.json`).
  A GitHub Actions workflow (`prefetch-fx.yml`) runs daily at 06:00 UTC
  and on `workflow_dispatch` to fetch missing rates and commit the updated
  cache. Vercel redeploys automatically on each push.
- A privacy notice on the form stating the CSV is processed in memory and
  never stored.
- No authentication (public access).
- Errors from malformed CSVs are returned as a plain browser error message.

The core scripts are refactored to expose a `process(csv_bytes, year,
fx_cache) -> dict[str, str]` function instead of reading/writing files
directly. The existing CLI entry points are preserved.

## Files to modify

- [ ] `src/yuh_csv_ifu.py` — refactor to expose `process()` returning a
      dict of filename→CSV string; keep existing CLI entry point working
- [ ] `src/wise_csv_ifu.py` — same refactor as above
- [ ] `src/unified_readme.py` — expose `generate()` accepting both outputs
      as dicts rather than reading from disk
- [ ] `src/fx_cache.py` (new or split from existing) — decouple FX cache
      from file path; accept a pre-loaded dict so the function can inject
      the bundled JSON
- [ ] `src/prefetch_fx.py` (new) — standalone script that fetches missing
      FX rates for a configurable date range and writes `src/fx_cache.json`
- [ ] `api/process.py` (new) — Vercel Python function: parse multipart
      upload, load bundled cache, call both processors, zip results, return
- [ ] `public/index.html` (new) — upload form: year selector, two optional
      file inputs, submit button, privacy notice, basic error display
- [ ] `.github/workflows/prefetch-fx.yml` (new) — daily + workflow_dispatch
      job that runs `prefetch_fx.py` and commits if cache changed
- [ ] `vercel.json` (new) — routes `api/*` to Python runtime

## Verification steps

- [ ] Upload a real Yuh CSV for a known year → ZIP contains the expected
      six output CSVs with correct gain figures.
- [ ] Upload a real Wise CSV for a known year → ZIP contains correct output.
- [ ] Upload both CSVs together → ZIP includes unified README.md.
- [ ] Upload only one of the two CSVs → the other is silently skipped, ZIP
      still valid.
- [ ] Upload a malformed CSV → browser shows a clear error message, no 500.
- [ ] Trigger the GH Action manually → `fx_cache.json` is updated and
      committed; Vercel redeploys.
- [ ] Run existing CLI scripts after refactor → output unchanged.
