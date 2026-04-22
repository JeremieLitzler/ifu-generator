# Feature: Unified tax summary per fiscal year (Yuh + Wise)

Created: 2026-04-22

## Context

`yuh_csv_ifu.py` and `wise_csv_ifu.py` each produce detailed CSV files and a
broker-specific README. When both accounts are held, the user needs a single view
of what to enter in the online French tax form — one number per box, not two
separate documents to reconcile manually.

## What `src/unified_readme.py` does

Reads the CSV outputs of the broker scripts and produces `ifu/<year>/README.md`
with one table per tax form, showing the exact values to type in:

| Form | Source data | Output |
|------|-------------|--------|
| **2074** | `ifu/yuh/<y>/<y>_gains_2074.csv` + `ifu/wise/<y>/<y>_gains_2074.csv` | Yuh + Wise totals, combined net gain/loss → case 3VG or 3VH |
| **2086** | `ifu/yuh/<y>/<y>_gains_2086.csv` | Informational only (crypto-ETPs) |
| **2042** | `ifu/yuh/<y>/<y>_dividendes.csv` | 2DC, 2TR, 2AB values |
| **3916** | Inferred from which broker CSVs are present | Checklist of accounts to declare |

Frais de gestion Wise are shown as informational (not deductible, no form entry).

## Usage

```bash
# Run broker scripts first
python src/yuh_csv_ifu.py  2024 --folder transactions
python src/wise_csv_ifu.py 2024 --folder transactions

# Then generate the unified summary
python src/unified_readme.py 2024

# Optional: override the ifu root directory
python src/unified_readme.py 2024 --ifu-root /path/to/ifu
```

Output: `ifu/<year>/README.md`

## Design decisions

- **Reads CSV outputs, not READMEs** — the broker CSVs are the structured data source;
  the README just presents them. Avoids fragile regex over Markdown.
- **One value per box** — the script answers "what do I type where?", not "here is the
  full computation detail" (that stays in the per-broker READMEs).
- **Graceful degradation** — works with only one broker's data if the other is absent.
- **No duplication of logic** — gain computation stays in the broker scripts; this
  script only sums the already-computed per-row gain columns.

## Files added

- `src/unified_readme.py` — the new script
