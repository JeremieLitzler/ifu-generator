# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Two scripts produce French tax declaration CSVs for French-resident cross-border workers (frontaliers) with a Yuh/Swissquote brokerage account. Both implement the PMP method (art. 150-0 D CGI) with ECB CHF→EUR rates via `api.frankfurter.dev`.

| Script               | Input                                           | Status                     |
| -------------------- | ----------------------------------------------- | -------------------------- |
| `src/yuh_csv_ifu.py` | Yearly CSV exports (`ACTIVITIES_REPORT-*.CSV`)  | **Active**                 |
| `yuh_ifu.py`         | Per-transaction PDF files (`TRANSACTION-*.PDF`) | Legacy, kept for reference |

## Running the CSV script (src/yuh_csv_ifu.py)

```bash
# Install dependency
pip install requests

# Run for a target year (reads all available CSVs for correct PMP)
python src/yuh_csv_ifu.py 2024 [--folder transactions] [--cache fx_cache.json]

# With late-declaration penalty estimate (shorthand flags)
python src/yuh_csv_ifu.py 2024 -s   # spontaneous correction (10 %)
python src/yuh_csv_ifu.py 2024 -f   # after formal notice (40 %)
python src/yuh_csv_ifu.py 2024 -ff  # fraud (80 %)
# Or explicitly:
python src/yuh_csv_ifu.py 2024 -cldp [--penalty-scenario {spontaneous,formal,fraud}] [--declaration-deadline YYYY-MM-DD]
```

The script reads **all** `ACTIVITIES_REPORT-*.CSV` files in `--folder` to compute the correct cumulative PMP, but outputs only the target year's transactions and gains.

Output directory: `ifu/<year>/yuh/`

- `<year>_transactions.csv` — year's operations with multi-currency→EUR conversion
- `<year>_gains_2074.csv` — capital gains for form 2074 (securities)
- `<year>_gains_2086.csv` — informational crypto-ETP gains for form 2086
- `<year>_dividendes.csv` — dividends/distributions
- `<year>_summary.csv` — positions + PMP at 31/12 of target year
- `<year>_fx_log.csv` — ECB rate log

## Supporting modules

- `src/constants.py` — `ACTIVITY_TYPE` string constants for all Yuh CSV row types
- `src/ticker_isin.py` — `TICKER_ISIN` dict mapping Yuh ticker → `(ISIN, name)`, plus `NON_SECURITY_ASSETS` and `TICKER_NAME_KEYWORDS` for dividend name matching. Update this file when new securities appear in the CSV exports.

## Architecture (src/yuh_csv_ifu.py)

1. **CSV parsing** (`parse_csv_file`) — reads `ACTIVITIES_REPORT-*.CSV` (UTF-8 BOM, semicolon-delimited). Filters: `INVEST_*` rows (buy/sell), `CASH_TRANSACTION_RELATED_OTHER` (dividends), `BANK_AUTO_ORDER_EXECUTED` "Autoexchange" (exchange fees logged separately). Resolves ticker→ISIN via `ticker_isin.py`.
2. **FX conversion** (`FXCache`) — persistent JSON cache keyed `"{date}_{currency}"`. Handles CHF, USD, and any other currency→EUR. Pass-through for EUR. Handles weekend/holiday BCE date shifting.
3. **PMP gain calculation** (`compute_gains`) — processes all transactions sorted by date+row_id; computes weighted average cost per ISIN; records realized gains on each sell.
4. **CSV output + console summary** — filters results to target year; writes six CSV files; prints French tax form summary.

## Key domain rules

- **Crypto-ETPs**: `CRYPTO_ETP_ISINS` in `src/yuh_csv_ifu.py` must be updated if new crypto-ETPs are held. Currently: WisdomTree BTC/ETH and others.
- **Cost basis** (buy) = `abs(DEBIT)` — includes Yuh commission. **Proceeds** (sell) = `CREDIT` — net of fees.
- **Auto-exchange fees** (`BANK_AUTO_ORDER_EXECUTED`): matched to the corresponding buy order by date + foreign currency. When exactly one buy exists on the same date in the same currency, the CHF fee is converted to EUR and added to that transaction's cost basis (`exchange_fee_eur`). If ambiguous (multiple candidates) or unmatched, reported as a lump sum with both CHF and EUR values.
- ECB rate on weekend/holiday → last business day's rate (standard DGFiP practice).
- `transactions/` CSV files and `guide-investissement-frontalier*.md` are gitignored (personal financial data).
