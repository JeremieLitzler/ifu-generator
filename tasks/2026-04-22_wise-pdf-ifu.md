# Task: Wise tax PDF → IFU script (wise_pdf_ifu.py)

Created: 2026-04-22

## Context

Wise (formerly TransferWise) provides an annual "Relevé fiscal sur les revenus, acquisitions, gains et pertes" PDF for its investment product (Wise Assets / Stocks). Unlike Yuh, **Wise does NOT export raw transaction CSVs for investments** — only PDF tax statements are available (confirmed by research + account inspection).

Key structural difference: **Wise uses FIFO** internally; French law requires **PMP** (art. 150-0 D CGI). The script must recompute gains using PMP from the raw per-transaction data inside the PDF.

PDFs follow the naming pattern `wise_tax_statement_YYYYMMDD_YYYYMMDD.pdf` in `transactions/`.

## Wise PDF structure (2024, 13 pages)

### Section II — "Gain en capital" (pages 4–9)

One FIFO lot per block. Headers repeated each page:

```csv
ISIN- N° de valeur- Nom | Date de valeur | Devise | Montant en Devise [cols] | Montant en EUR [cols]
Transaction              |                |        | Qty | Prix | Frais | Tx | Accrued | Total | Wtax | FX | Total | Frais
```

Data rows (9 numeric fields after type, date, devise):

```csv
Achat  DD.MM.YYYY  EUR  <qty>   <-prix>  0,00  0,00  <-total>  0,00  1,0000  <-total_eur>  0,00
Vente  DD.MM.YYYY  EUR  <-qty>  <prix>   0,00  0,00  <total>   0,00  1,0000  <total_eur>   0,00
Gains/Pertes  <fifo_gain>
```

Field mapping (0-indexed from first numeric):

| Index | Column                        | Notes                                                       |
| ----- | ----------------------------- | ----------------------------------------------------------- |
| 0     | Quantité/Nominal              | Positive=buy, negative=sell                                 |
| 1     | Prix unitaire                 | Negative for buy (cost direction), positive for sell        |
| 2     | Frais de transaction (Devise) | Always 0,00 for Wise                                        |
| 3     | Transaction/Intérêts courus   | Always 0,00 in observed data                                |
| 4     | Total (Devise)                | Negative for buy, positive for sell                         |
| 5     | Taxe à la source              | 0,00 (no withholding)                                       |
| 6     | Taux de change                | 1,0000 for EUR transactions                                 |
| 7     | Total (EUR)                   | Negative for buy, positive for sell — **key field for PMP** |
| 8     | Frais de transaction (EUR)    | 0,00 for Wise                                               |

Section sub-headers (to track ISIN context):

- `Fonds` — category header
- `Irlande` / `Luxembourg` — country
- `IE00B41N0724 - EUR Interest fund` — ISIN + fund name

### Section III — "Autres Opérations" (page 10)

Monthly platform management fees (4 numeric fields after type, date, devise):

```
Frais  DD.MM.YYYY  EUR  1,000000  <-amount>  1,0000  <-amount_eur>
```

Fields: Quantité, Total (Devise), Taux de change, Total (EUR).

Fees are charged monthly (one debit per month assets are held).

## Known fund ISINs (Wise Assets)

| ISIN           | Name              | Country    | Type                                   | FX  |
| -------------- | ----------------- | ---------- | -------------------------------------- | --- |
| `IE00B41N0724` | EUR Interest fund | Irlande    | Monetary (BlackRock ICS EUR Liquidity) | EUR |
| `LU0852473015` | Stocks fund       | Luxembourg | MSCI World Index (iShares)             | EUR |

Sources:

- [Wise – Understanding taxes when using Wise Interest or Stocks](https://wise.com/help/articles/1yIMYUKchCnDYxP1pn5B5t/understanding-taxes-when-using-wise-interest-or-stocks)
- [Wise – Holding your money as Stocks](https://wise.com/help/articles/3luodUQFD9YWzNc8PvIfVK/holding-your-money-as-stocks)
- PDF Section II headers confirmed from `wise_tax_statement_20240101_20241231.pdf`

Both funds are **accumulating** (no dividend distributions). Both domiciled in IE/LU → 0% withholding.
Both classify as **valeurs mobilières → formulaire 2074** (not crypto, not actifs numériques).

## Key difference vs Yuh script

| Aspect                       | Yuh (CSV)                           | Wise (PDF)                                                |
| ---------------------------- | ----------------------------------- | --------------------------------------------------------- |
| Input                        | `ACTIVITIES_REPORT-YYYY.CSV`        | `wise_tax_statement_YYYYMMDD_YYYYMMDD.pdf`                |
| Cost basis method (platform) | N/A                                 | FIFO                                                      |
| Cost basis (French law)      | **PMP** (recomputed)                | **PMP** (must recompute from PDF data)                    |
| FX conversion                | CHF/USD→EUR via BCE                 | EUR in 2024 (fx=1.0); BCE for other currencies            |
| Fees                         | Auto-exchange fee attributed to buy | Monthly management fee — NOT added to cost basis          |
| Crypto-ETPs                  | Yes (BTCW, ETHW…)                   | None identified                                           |
| No-CSV limitation            | N/A                                 | **CRITICAL: unrealized positions NOT in PDF** (see below) |

## Critical limitation: unrealized positions not in PDF

Wise's PDF (§9.2 of explanatory notes) states:

> "Seuls les renseignements relatifs à la vente sont inscrits dans l'historique des opérations, ce qui signifie que les renseignements historiques d'un titre qui a déjà fait l'objet d'une disposition intégrale aux fins fiscales avant une nouvelle acquisition ne sont pas indiqués."

In practice: **only buys matched (FIFO) to that year's sells appear in the PDF**. Buys for still-held positions at 31/12 are absent.

In 2024 this is not an issue (all positions were fully closed within the year). But in future years, if positions are held at 31/12, the script will undercount the cost basis for the next year's PMP computation.

**Workaround**: chain all year PDFs. For each year, parse ALL available Wise PDFs to accumulate the complete buy history before computing PMP on the target year. Even so, the fundamental limitation remains if open-position buys were never in any PDF.

**TODO**: When the user has open positions at year-end, Wise should provide those buy dates/prices via the account app ("Assets" section). Manual CSV supplement may be needed.

## Tax treatment of management fees (Section III)

Monthly fees are debited directly from the Wise account. They are NOT embedded in the NAV.

- **Under PFU (flat tax 30%)**: NOT deductible from capital gains (art. 150-0 D CGI does not allow deduction of ongoing management fees under PFU)
- **Under barème progressif (option)**: possibly deductible as "frais de gestion" — needs case-by-case verification
- **Script behavior**: log fees in `*_fees.csv`, do NOT include in cost basis, flag in summary

Reference: BOI-RPPM-PVBMI-20-10-10-10 §120 (frais déductibles) — ongoing management fees for portfolio accounts are not acquisition costs.

## Dependency

```bash
pip install pdfplumber requests
```

`pdfplumber` is not in the current dependencies (only `requests`). Must be added to any install instructions.

## Files to create / modify

- [x] Create `src/wise_pdf_ifu.py` — PDF parser + PMP recomputation + 6 CSV outputs
- [ ] Validate PDF text extraction: run script and verify all transaction rows are captured (cross-check totals against Section I summary)
- [ ] Validate PMP vs FIFO comparison: PMP gain will differ from Wise's FIFO total when buys at different prices exist. Document the delta.
- [ ] Update `CLAUDE.md` to mention `wise_pdf_ifu.py`
- [ ] Add 3916 reminder for Wise account to script summary

## Checklist

- [ ] pdfplumber text extraction works on actual PDFs (regex may need tuning)
- [ ] All transaction rows captured for both ISINs
- [ ] PMP gain computed and compared against Wise's FIFO total (from Section I)
- [ ] Section III fees parsed correctly (total matches Section I "Frais de transaction")
- [ ] FXCache used for non-EUR transactions (robustness)
- [ ] Console summary matches yuh_csv_ifu.py format
- [ ] Open-position warning when sum(buys) ≠ sum(sells) per ISIN
