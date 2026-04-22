# Task: Convert yuh_ifu.py to use CSV exports instead of PDF files

Created: 2026-04-22

## Context

`yuh_ifu.py` currently parses individual `TRANSACTION-*.PDF` files downloaded one by one from the Yuh app. Yuh also provides yearly activity CSV exports (`ACTIVITIES_REPORT-YYYY.CSV`) that contain all transactions in a structured format — far easier to parse reliably.

The guide (`guide-investissement-frontalier-specific.md`) documents the full fiscal context: PMP method, CHF→EUR BCE rates, French tax forms (2074, 2086, 3916), and the distinction between valeurs mobilières and actifs numériques.

## CSV format (semicolon-delimited, UTF-8 BOM)

```
DATE;ACTIVITY TYPE;ACTIVITY NAME;DEBIT;DEBIT CURRENCY;CREDIT;CREDIT CURRENCY;
CARD NUMBER;LOCALITY;RECIPIENT;SENDER;FEES/COMMISSION;BUY/SELL;QUANTITY;ASSET;PRICE PER UNIT
```

### Date format

`DD/MM/YYYY`

### Activity types (see `constants.py`)

| Type                              | Fiscal relevance                                         |
| --------------------------------- | -------------------------------------------------------- |
| `INVEST_ORDER_EXECUTED`           | Manual buy/sell — core tax event                         |
| `INVEST_RECURRING_ORDER_EXECUTED` | Recurring buy/sell — core tax event                      |
| `INVEST_RECURRING_ORDER_REJECTED` | Ignored (no transaction occurred)                        |
| `BANK_AUTO_ORDER_EXECUTED`        | CHF→USD/EUR auto-exchange (not a securities transaction) |
| `BANK_ORDER_EXECUTED`             | Manual CHF↔EUR exchange                                  |
| `CASH_TRANSACTION_RELATED_OTHER`  | Dividends / distributions (e.g. `S&P 500 Dividend`)      |
| `CASH_TRANSACTION_OTHER`          | Other cash movements                                     |
| `PAYMENT_TRANSACTION_IN`          | Incoming transfer (salary, Wise, etc.) — ignored         |
| `PAYMENT_TRANSACTION_OUT`         | Outgoing transfer (Wise, etc.) — ignored                 |
| `REWARD_RECEIVED`                 | SWQ bonus — ignored for tax                              |

The data to read is only the ones where `ACTIVITY TYPE`:

- starts with `INVEST_` (actual buy or sell investments)
- is `CASH_TRANSACTION_RELATED_OTHER` which can be dividend payments
- is `BANK_AUTO_ORDER_EXECUTED` with a `ACTIVITY NAME` starting with "Autoexchange Swiss francs" (that corresponds to a automatic exchange of CHF to a currency for an investment).

### Key field notes

- `DEBIT` is negative (e.g. `-76.11`). `CREDIT` is positive. One of the two is always empty.
- `FEES/COMMISSION`: fee in the transaction currency (e.g. `1.11` USD for an invest order).
- `BUY/SELL`: `BUY` or `SELL` for invest orders; empty otherwise.
- `QUANTITY`: number of units bought/sold (fractional shares possible).
- `ASSET`: ticker symbol (e.g. `VUSD`, `VWRD`, `IWDC`). Not the ISIN — needs a mapping.
- `PRICE PER UNIT`: price per share in the transaction currency; also used as the FX rate for `BANK_AUTO_ORDER_EXECUTED` rows (CHF per foreign currency unit).
- `ACTIVITY NAME`: free text in triple-quoted form, e.g. `"""0.8682x S&P 500 (Vanguard S&P 500)"""`. Contains quantity + security name.

### Buy/sell cost basis logic

For `INVEST_ORDER_EXECUTED` / `INVEST_RECURRING_ORDER_EXECUTED`:

- **Buy**: cost = `abs(DEBIT)` in DEBIT_CURRENCY (fees already included in the debit amount, as confirmed by the PDF-based logic).
- **Sell**: proceeds = `CREDIT` in CREDIT_CURRENCY (net of fees).
- Fee column (`FEES/COMMISSION`) is for reference; the debit/credit amounts are the source of truth.

### Dividend detection

`CASH_TRANSACTION_RELATED_OTHER` rows whose `ACTIVITY NAME` contains `Dividend`, `Distribution`, `Coupon`, or `Income`. Credit amount + currency = gross dividend received.

## What the new script must do

1. **Accept a year (4 digits)** as input to find the appropriate CSV file (e.g. `ACTIVITIES_REPORT-2023.CSV` or `ACTIVITIES_REPORT-2024.CSV`) in the folder `transactions` by default. Make folder value an option.
2. **Parse all relevant rows** by activity type using `constants.py`.
3. **Resolve ASSET ticker**: build a ticker-to-ISIN mapping (hardcoded dict at first) from `investments-product-details/README.md`. The same folder contains the ISIN in the factsheets PDF. Log a warning for unknown tickers.
4. **Convert all amounts to EUR** using the BCE FX cache (same `FXCache` class, same `api.frankfurter.dev` API). Currency is in `DEBIT CURRENCY` / `CREDIT CURRENCY` columns — may be CHF, EUR, USD, or other.
5. **Compute PMP gains** using the same `compute_gains()` logic (PMP method, art. 150-0 D CGI).
6. **Produce the same six output CSV files** per year as the current script:
   - `*_transactions.csv`
   - `*_gains_2074.csv`
   - `*_gains_2086.csv`
   - `*_dividendes.csv`
   - `*_summary.csv`
   - `*_fx_log.csv`
7. **Print the same console summary** grouped by year.

## Ticker → ISIN mapping (from factsheets + CSV analysis)

Confirmed from factsheet PDFs in `investments-product-details/`:

| Ticker | ISIN | Notes |
|--------|------|-------|
| `BTCW` | `GB00BJYDH287` | WisdomTree Physical Bitcoin — crypto-ETP |
| `ETHW` | `GB00BJYDH394` | WisdomTree Physical Ethereum — crypto-ETP |
| `ZGLD` | `CH0139101593` | Swisscanto Gold ETF (CHF, distributing) |
| `IWDC` | `IE00B8BVCK12` | iShares MSCI World CHF Hedged UCITS ETF |
| `XMME` | `IE00BTJRMP35` | Xtrackers MSCI Emerging Markets UCITS ETF |
| `VUSD` | `IE00B3XXRP09` | Vanguard S&P 500 UCITS ETF (USD, distributing) |
| `VWRD` | `IE00B3RBWM25` | Vanguard FTSE All-World UCITS ETF (USD, distributing) |
| `MVSH` | `IE00BD1JRZ09` | iShares MSCI World Min Vol Factor UCITS ETF |

Non-security codes to ignore: `SWQ`, `CHF`, `EUR`, `USD`.

## New challenges vs. PDF version

- **No ISIN in the CSV**: must map `ASSET` ticker → ISIN using `ticker_isin.py` (see table above). Warn and skip on unknown.
- **Multi-currency**: transactions can be in CHF, USD, EUR. The FX cache must handle CHF→EUR, USD→EUR, and pass-through for EUR.
- **Exchange rows (`BANK_AUTO_ORDER_EXECUTED`)**: these are currency conversions, not securities transactions. They should be ignored for PMP/gains but could optionally be logged. However, the fee amount must be taken into account as fees to purchase the securities.
- **`PRICE PER UNIT` for exchange rows**: this column holds the FX rate (CHF per unit of foreign currency), not a securities price.
- **BOM in CSV**: files start with a UTF-8 BOM (`\ufeff`) — use `encoding='utf-8-sig'` when opening.
- **Triple-quoted activity names**: strip surrounding `"""` from `ACTIVITY NAME`.

## Files to create / modify

- [ ] Create `yuh_csv_ifu.py` — new main script (keep `yuh_ifu.py` untouched for reference)
- [ ] Create `ticker_isin.py` — ticker→ISIN mapping dict, populated from known holdings
- [ ] Update `constants.py` if additional constants are needed
- [ ] Update `CLAUDE.md` to document the new script

## Out of scope

- Migrating the PDF parser (keep `yuh_ifu.py` as-is)
- Report "des moins-values sur 10 ans" (still manual)
- "Retenue à la source suisse" on distributions
