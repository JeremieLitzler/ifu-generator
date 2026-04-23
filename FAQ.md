# FAQ

## What is ifu-generator?

A set of Python scripts that generate French tax declaration data for French-resident cross-border workers (frontaliers) who hold investment accounts at Yuh/Swissquote and/or Wise Assets. It produces CSVs ready to fill in forms 2074, 2086, and 2042.

---

## Is the README meant for users or developers?

The README is for **users**: it covers what the tool does, which brokers are supported, how to run the scripts, what output files are produced, and which tax rules are applied. No Python internals.

`CLAUDE.md` is for **developers/Claude Code**: it covers the script inventory, internal architecture (parsing, FX cache, PMP logic), and implementation rules.

---

## What documentation files exist and what do they cover?

| File | Audience | Content |
|------|----------|---------|
| `README.md` | Users | Business usage — brokers, IFU forms, commands, output files, tax rules |
| `CLAUDE.md` | Developers / Claude Code | Technical details — script inventory, architecture, implementation rules |
| `FAQ.md` | Users | Common questions about the project |
| `CALCULATIONS_ACCURACY.md` | Users / Developers | Confidence levels per computation area |

---

## Which scripts exist and what do they do?

| Script | Purpose |
|--------|---------|
| `src/yuh_csv_ifu.py` | Processes Yuh/Swissquote CSV exports → IFU CSVs |
| `src/wise_csv_ifu.py` | Processes Wise Assets CSV exports → IFU CSVs (primary) |
| `src/wise_pdf_ifu.py` | Processes Wise annual PDF tax statement → IFU CSVs (cross-check / fallback) |
| `src/unified_readme.py` | Merges Yuh + Wise outputs into a single `ifu/<year>/README.md` |
| `src/fees_by_activity.py` | Debug utility: groups Yuh fees by activity type |
| `src/constants.py` | Activity type constants for Yuh CSV rows |
| `src/ticker_isin.py` | Ticker → ISIN mapping for Yuh securities |

---

## What shell wrappers are in `scripts/` and how do I use them?

| Script | Calls | Usage |
|--------|-------|-------|
| `scripts/generate_ifu_yuh.sh` | `src/yuh_csv_ifu.py` | `bash scripts/generate_ifu_yuh.sh <year> [options]` |
| `scripts/generate_ifu_wise.sh` | `src/wise_csv_ifu.py` | `bash scripts/generate_ifu_wise.sh <year> [options]` |

Both wrappers pass all arguments through to the underlying Python script (`"$@"`), so every optional flag — `--folder`, `--cache`, `-s`, `-f`, `-ff` — works exactly as documented for the Python scripts.

```bash
# Examples
bash scripts/generate_ifu_yuh.sh 2024
bash scripts/generate_ifu_wise.sh 2024 --folder transactions -s
```

---

## What filename format does `yuh_csv_ifu.py` expect for input CSV files?

Files must be named `yuh_ACTIVITIES_REPORT-<year>.CSV` (or `.csv`) and placed inside the folder specified by `--folder` (default: `transactions/`). The `yuh_` prefix distinguishes Yuh exports from Wise files when both brokers' exports share the same folder.

Example: `transactions/yuh_ACTIVITIES_REPORT-2024.CSV`

---

## What happened to `generate_ifu.sh`?

It was renamed to `generate_ifu_yuh.sh` to match the broker-specific naming convention alongside `generate_ifu_wise.sh`. There is no longer a generic `generate_ifu.sh`.

---

## What is the PMP method?

PMP (*Prix Moyen Pondéré*) is the weighted average cost method required by French tax law (art. 150-0 D CGI) to compute capital gains on securities. Each buy updates the average cost per share; each sell computes the gain against that average.

---

## What exchange rate is used for CHF/USD → EUR conversion?

ECB (European Central Bank) rates fetched via `api.frankfurter.dev`. If a transaction falls on a weekend or public holiday, the last business day's rate is used — the standard DGFiP practice.

---

## Are broker commissions included in the cost basis?

Yes. For Yuh, the cost basis of a buy = `abs(DEBIT)`, which includes the Yuh commission. Auto-exchange fees (`BANK_AUTO_ORDER_EXECUTED`) are also added to the cost basis of the corresponding buy order, as they are *frais d'acquisition* under the PMP method.

---

## Are Wise management fees deductible?

No — and this applies under **both** PFU and the barème progressif option.

Art. 150-0 D CGI defines the capital gain as `prix de cession − prix de revient`. The *prix de revient* can only include the acquisition price plus **frais d'acquisition** — fees paid *at the moment of buying* (brokerage commissions, transaction taxes). Wise's monthly platform fees are *frais de gestion courants* (ongoing management charges), not frais d'acquisition, so they cannot be added to the cost basis under either tax regime.

The historical deduction for *frais de garde* that existed before 2018 applied only to *revenus de capitaux mobiliers* (dividends, interest), not to capital gains — and was suppressed by the Finance Law 2017 alongside the introduction of PFU.

The fees are logged in `<year>_fees.csv` for records but have no impact on the computed gain.

---

## How are crypto-ETPs handled?

Gains on crypto-ETPs (e.g. WisdomTree BTC/ETH) are reported separately in `<year>_gains_2086.csv` for form 2086. The list of crypto-ETP ISINs is maintained in `CRYPTO_ETP_ISINS` inside `src/yuh_csv_ifu.py` and must be updated when new ones are held.

---

## What do the penalty flags do?

They estimate late-declaration interest on top of the tax owed:

| Flag | Scenario | Rate |
|------|----------|------|
| `-s` | Spontaneous correction | 10 % |
| `-f` | After formal notice | 40 % |
| `-ff` | Fraud | 80 % |

Pass the flag to any of the three scripts (`yuh_csv_ifu.py`, `wise_csv_ifu.py`, `unified_readme.py`).

---

## What is the output directory structure under `ifu/`?

```
ifu/
├── yuh/
│   └── <year>/       ← yuh_csv_ifu.py output (gains, dividends, summary…)
├── wise/
│   └── <year>/       ← wise_csv_ifu.py output
└── <year>/
    └── README.md     ← unified_readme.py consolidated summary
```

Broker-specific outputs are grouped by broker then year. The unified README sits at the year level so all data for a given fiscal year is visible in one place.

---

## What does `unified_readme.py` produce?

A single `ifu/<year>/README.md` with one table per tax form, showing the exact values to type into the online French tax return:

- **Formulaire 2074** — Yuh and Wise gains shown separately, then combined with the final case (3VG or 3VH) and rounded integer to enter.
- **Formulaire 2042** — 2DC, 2TR, and 2AB values from Yuh dividends.
- **Formulaire 3916** — checklist of foreign accounts to declare (inferred from which broker data is present).
- **Penalty block** — if a `-s`/`-f`/`-ff` flag is passed, the late-declaration penalty estimate for the combined gain.

Run it after both broker scripts have generated their CSVs for the year.

---

## Are penalty amounts rounded to the nearest euro?

Yes. The DGFiP rounds all tax amounts to the nearest euro. The penalty chain is:

```
net_gain_rounded  = round(net_gain)           # the integer entered on the form
tax_owed          = round(net_gain_rounded × 0.30)
late_interest     = round(tax_owed × 0.002 × months_delay)
surcharge         = round(tax_owed × penalty_rate)
total_due         = tax_owed + late_interest + surcharge
```

All three scripts (`yuh_csv_ifu.py`, `wise_csv_ifu.py`, `unified_readme.py`) follow this chain.

---

## What is the SIP?

**Service des Impôts des Particuliers** — the local French tax office handling individual taxpayers. It is where you go (in person, by phone, or via your online *espace particulier*) to regularize a late declaration, ask a tax question, or negotiate a payment plan.

---

## Which files are gitignored?

- `transactions/` — personal CSV exports from Yuh and Wise
- `guide-investissement-frontalier*.md` — personal reference documents
- `ifu/` output files (optional, depending on local config)

---

## Does Wise provide raw transaction data for investments?

Yes, via two formats:

| Format | File pattern | Use |
|--------|-------------|-----|
| CSV | `wise_assets_statement_*.csv` | **Primary input** — complete raw history (BUY, SELL, FEE_CHARGE rows) including unrealized positions |
| PDF | `wise_tax_statement_*.pdf` | Cross-check only — pre-computed FIFO summary; does not include buys for positions still held at year-end |

The CSV is exported from the Wise account under Assets → Statement. The PDF is the annual tax report produced by Wise.

---

## Why does the Wise script recompute gains instead of using the annual PDF tax report?

Two reasons:

1. **Wrong method**: Wise's PDF uses FIFO (*First In First Out*). French law (art. 150-0 D CGI) requires PMP (*Prix Moyen Pondéré*). The two methods give different results whenever shares bought at different prices are partially sold.

2. **Incomplete history**: The PDF only lists buys that are FIFO-matched to that year's sells. Buys for positions still held at 31 December are absent, making it impossible to compute a correct PMP for future years from the PDF alone.

The raw CSV contains all transactions and is sufficient for an exact PMP computation.

---

## What is the difference between `wise_csv_ifu.py` and `wise_pdf_ifu.py`?

| | `wise_csv_ifu.py` | `wise_pdf_ifu.py` |
|-|-------------------|-------------------|
| Input | `wise_assets_statement_*.csv` | `wise_tax_statement_*.pdf` |
| History | Complete (all buys including unrealized) | Partial (only FIFO-matched buys) |
| Parsing | Simple CSV reader | PDF text extraction via `pdfplumber` |
| Use | **Primary — run this** | Cross-check / fallback |
| Extra dependency | none beyond `requests` | `pip install pdfplumber` |

Use `wise_pdf_ifu.py` only to sanity-check totals against Wise's own FIFO numbers.

---

## Can I optimise my Wise holdings for tax efficiency?

From a tax mechanics standpoint only (not investment advice):

- **Accumulating funds are already optimal**: `LU0852473015` (MSCI World) and `IE00B41N0724` (EUR Interest) reinvest internally — no dividend tax drag, gains taxed only on disposal.
- **Frequent small buy/sell cycles** (Wise's automatic rebalancing) do not create a tax inefficiency under PMP: partial sells against an average cost basis produce the same net gain as a single larger sell, mathematically.
- **Management fees** are the main cost drag, but as noted above they cannot offset the tax. This is a structural limitation of holding through a platform that charges external fees rather than embedding them in the NAV.

For questions about whether to switch platforms, change allocation, or restructure holdings, consult a *conseil en gestion de patrimoine* (CGP) who knows your full financial picture.
