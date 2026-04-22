# ifu-generator

Generates French tax declaration data (IFU equivalent) for French-resident cross-border workers (frontaliers) holding investment accounts at **Yuh/Swissquote** and/or **Wise Assets**.

Implements the **PMP method** (art. 150-0 D CGI) with ECB CHF→EUR exchange rates. Produces CSVs ready to fill in forms 2074, 2086, and 2042.

---

## Supported brokers

| Broker | Input files | Output folder |
|--------|------------|---------------|
| Yuh / Swissquote | `ACTIVITIES_REPORT-*.CSV` | `ifu/<year>/yuh/` |
| Wise Assets | `wise_assets_statement_*.csv` | `ifu/<year>/wise/` |

---

## Prerequisites

```bash
pip install requests
```

---

## Usage — Yuh / Swissquote

```bash
bash scripts/generate_ifu_yuh.sh <year> [--folder <dir>] [--cache fx_cache.json]
```

Or directly:

```bash
python src/yuh_csv_ifu.py 2024 [--folder transactions] [--cache fx_cache.json]
```

**With late-declaration penalty estimate:**

```bash
python src/yuh_csv_ifu.py 2024 -s    # spontaneous correction (10 %)
python src/yuh_csv_ifu.py 2024 -f    # after formal notice (40 %)
python src/yuh_csv_ifu.py 2024 -ff   # fraud (80 %)
```

**Output files** in `ifu/<year>/yuh/`:

| File | Content |
|------|---------|
| `<year>_transactions.csv` | All operations with CHF/USD→EUR conversion |
| `<year>_gains_2074.csv` | Capital gains/losses → form 2074 (securities) |
| `<year>_gains_2086.csv` | Crypto-ETP gains → form 2086 (informational) |
| `<year>_dividendes.csv` | Dividends and distributions |
| `<year>_summary.csv` | Positions and PMP at 31/12 |
| `<year>_fx_log.csv` | ECB rates used |

---

## Usage — Wise Assets

```bash
bash scripts/generate_ifu_wise.sh <year> [--folder <dir>] [--cache fx_cache.json]
```

Or directly:

```bash
python src/wise_csv_ifu.py 2024 [--folder transactions] [--cache fx_cache.json]
```

Same penalty flags (`-s`, `-f`, `-ff`) apply.

**Output files** in `ifu/<year>/wise/`:

| File | Content |
|------|---------|
| `<year>_transactions.csv` | All operations with EUR conversion |
| `<year>_gains_2074.csv` | Capital gains/losses → form 2074 |
| `<year>_dividendes.csv` | Dividends (empty for accumulating funds) |
| `<year>_fees.csv` | Monthly management fees (not deductible under PFU) |
| `<year>_summary.csv` | Positions and PMP at 31/12 |
| `<year>_fx_log.csv` | ECB rates used |

---

## Usage — Unified summary (Yuh + Wise)

After running both scripts, generate a consolidated report:

```bash
python src/unified_readme.py 2024 [--ifu-root ifu] [-s|-f|-ff]
```

Produces `ifu/<year>/README.md` with exact amounts to enter per tax form line (2074, 2042).

---

## Key tax rules applied

- **PMP method** — weighted average cost basis, recomputed from full transaction history
- **Cost basis** includes broker commissions and auto-exchange fees (frais d'acquisition)
- **ECB rate** on weekends/holidays → last business day (standard DGFiP practice)
- **Crypto-ETPs** (WisdomTree BTC/ETH, etc.) reported separately on form 2086
