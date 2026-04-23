# Task: Wise Assets → IFU scripts

Created: 2026-04-22
Updated: 2026-04-23 — wise_pdf_ifu.py removed; CSV-only approach confirmed

## Context

Wise provides two data sources for its investment product (Wise Assets / Stocks):

1. **`wise_assets_statement_*.csv`** — raw transaction export (BUY, SELL, FEE_CHARGE rows). **Only input.** Contains full history including unrealized positions.
2. **`wise_tax_statement_*.pdf`** — annual FIFO tax summary (KPMG). Reference only; no script parses it. Does NOT include buys for positions held at year-end.

Key structural difference: **Wise uses FIFO** internally; French law requires **PMP** (art. 150-0 D CGI). `wise_csv_ifu.py` recomputes gains using PMP from the raw transaction data.

## CSV format (`wise_assets_statement_*.csv`)

Header:

```
Traded Asset ID Type, Traded Asset ID Value, Execution Date, Transaction Type,
Traded Units, Asset Base Currency, Asset Base Currency Unit Price Amount,
Asset Base Currency Value Traded, Settlement Date, Settlement Currency,
Settlement Amount, Settlement Conversion Rate, Settlement Conversion Rate Timestamp,
Legal Entity, Wise ID
```

### BUY / SELL rows

| Column                                  | Notes                                                          |
| --------------------------------------- | -------------------------------------------------------------- |
| `Traded Asset ID Type`                  | `ISIN`                                                         |
| `Traded Asset ID Value`                 | ISIN code (e.g. `LU0852473015`)                                |
| `Execution Date`                        | ISO 8601 UTC — use as transaction date                         |
| `Transaction Type`                      | `BUY` or `SELL`                                                |
| `Traded Units`                          | quantity (always positive)                                     |
| `Asset Base Currency`                   | `EUR`                                                          |
| `Asset Base Currency Unit Price Amount` | unit price                                                     |
| `Asset Base Currency Value Traded`      | units × price                                                  |
| `Settlement Currency`                   | `EUR`                                                          |
| `Settlement Amount`                     | amount paid/received — **key field for PMP** (always positive) |
| `Settlement Conversion Rate`            | FX rate (1.0 for EUR)                                          |
| `Wise ID`                               | UUID                                                           |

Cost basis (buy) = `Settlement Amount`. Proceeds (sell) = `Settlement Amount`.

### FEE_CHARGE rows

`Traded Asset ID *`, `Execution Date`, `Traded Units`, `Asset Base Currency *` are empty.

| Column                | Notes                          |
| --------------------- | ------------------------------ |
| `Transaction Type`    | `FEE_CHARGE`                   |
| `Settlement Date`     | ISO 8601 UTC — use as fee date |
| `Settlement Currency` | `EUR`                          |
| `Settlement Amount`   | fee amount (positive)          |

Monthly platform management fee. **Not an acquisition cost** → NOT added to cost basis.

## PDF format (`wise_tax_statement_*.pdf`) — reference only

### Section II — "Gain en capital"

One FIFO lot per block. Data rows (9 numeric fields after type, date, devise):

```
Achat  DD.MM.YYYY  EUR  <qty>   <-prix>  0,00  0,00  <-total>  0,00  1,0000  <-total_eur>  0,00
Vente  DD.MM.YYYY  EUR  <-qty>  <prix>   0,00  0,00  <total>   0,00  1,0000  <total_eur>   0,00
Gains/Pertes  <fifo_gain>
```

Field mapping (0-indexed from first numeric):

| Index | Column                        | Notes                               |
| ----- | ----------------------------- | ----------------------------------- |
| 0     | Quantité/Nominal              | Positive=buy, negative=sell         |
| 1     | Prix unitaire                 | Negative for buy, positive for sell |
| 2     | Frais de transaction (Devise) | Always 0,00                         |
| 3     | Transaction/Intérêts courus   | Always 0,00                         |
| 4     | Total (Devise)                | Negative for buy, positive for sell |
| 5     | Taxe à la source              | 0,00                                |
| 6     | Taux de change                | 1,0000 for EUR                      |
| 7     | Total (EUR)                   | **Key field**                       |
| 8     | Frais de transaction (EUR)    | 0,00                                |

### Section III — "Autres Opérations"

Monthly fees (4 numeric fields after type, date, devise):

```
Frais  DD.MM.YYYY  EUR  1,000000  <-amount>  1,0000  <-amount_eur>
```

**PDF critical limitation (§9.2)**: only buys matched to that year's sells appear. Buys for unrealized positions at 31/12 are absent → PMP would be incomplete for multi-year holding periods. CSV does not have this limitation.

## Known fund ISINs (Wise Assets)

| ISIN           | Name              | Country    | Type                                   | FX  |
| -------------- | ----------------- | ---------- | -------------------------------------- | --- |
| `IE00B41N0724` | EUR Interest fund | Irlande    | Monetary (BlackRock ICS EUR Liquidity) | EUR |
| `LU0852473015` | Stocks fund       | Luxembourg | MSCI World Index (iShares)             | EUR |

Sources:

- [Wise – Understanding taxes when using Wise Interest or Stocks](https://wise.com/help/articles/1yIMYUKchCnDYxP1pn5B5t/understanding-taxes-when-using-wise-interest-or-stocks)
- [Wise – Holding your money as Stocks](https://wise.com/help/articles/3luodUQFD9YWzNc8PvIfVK/holding-your-money-as-stocks)

Both funds are **accumulating** (no dividend distributions). Both domiciled in IE/LU → 0% withholding.
Both classify as **valeurs mobilières → formulaire 2074** (not crypto, not actifs numériques).

## Key difference vs Yuh script

| Aspect                       | Yuh (CSV)                             | Wise (CSV)                                 |
| ---------------------------- | ------------------------------------- | ------------------------------------------ |
| Input                        | `yuh_ACTIVITIES_REPORT-YYYY.CSV`      | `wise_assets_statement_*.csv`              |
| Cost basis method (platform) | N/A                                   | FIFO (ignored)                             |
| Cost basis (French law)      | **PMP** (recomputed)                  | **PMP** (recomputed)                       |
| FX conversion                | CHF/USD→EUR via BCE                   | EUR only (taux=1.0 in observed data)       |
| Fees                         | Auto-exchange fee → added to buy cost | Monthly management fee → separate CSV only |
| Crypto-ETPs                  | Yes (BTCW, ETHW…)                     | None identified                            |
| Date field                   | `DATE` column (DD/MM/YYYY)            | `Execution Date` (ISO 8601 UTC)            |

## Tax treatment of management fees

Monthly fees debited directly from the Wise account. NOT embedded in NAV.

- **Under PFU (30%)**: NOT deductible (art. 150-0 D CGI)
- **Under barème progressif**: possibly deductible as "frais de gestion" — case-by-case
- **Script behavior**: log in `*_fees.csv`, do NOT include in cost basis

Reference: BOI-RPPM-PVBMI-20-10-10-10 §120.

## Dependencies

```bash
pip install requests          # wise_csv_ifu.py
```

## Files

- [x] `src/wise_csv_ifu.py` — only script (CSV input, PMP, 6 CSV outputs)
- [x] ~~`src/wise_pdf_ifu.py`~~ — removed; PDF parsing dropped in favour of CSV-only approach
- [x] `CLAUDE.md` updated to document `wise_csv_ifu.py`
- [ ] Run `wise_csv_ifu.py 2024` and validate:
  - All BUY/SELL rows parsed for both ISINs
  - FEE_CHARGE rows captured

## Checklist

- [ ] `wise_csv_ifu.py 2024` runs without error
- [ ] BUY rows for unrealized positions (held at 31/12) are included in PMP base
- [ ] FEE_CHARGE dates parsed correctly from Settlement Date (no Execution Date)
- [ ] FXCache used for non-EUR transactions (robustness — not needed in current data)
- [ ] Console summary matches yuh_csv_ifu.py format
