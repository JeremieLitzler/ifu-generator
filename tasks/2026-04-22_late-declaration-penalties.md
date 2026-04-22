# Feature: Late declaration penalties for Formulaire 2074

Created: 2026-04-22

## Context

French-resident cross-border workers (frontaliers) may have omitted to declare capital
gains on their `formulaire 2074` in a prior year. The DGFiP applies:

- **Intérêts de retard** : 0.20 % per month of delay on the tax owed (2.4 % per year).
- **Majoration** : varies by scenario —
  - 10 % for a spontaneous correction filed before any formal notice (*mise en demeure*)
  - 40 % after a formal notice
  - 80 % in case of proven fraud (*manœuvres frauduleuses*)

Only **net positive gains** on Formulaire 2074 (securities, including crypto-ETPs
treated as *valeurs mobilières*) generate a tax liability. Losses produce no penalty.

The PFU (*prélèvement forfaitaire unique*) rate is **30 %** (12.8 % IR + 17.2 %
prélèvements sociaux). This is the rate applied to net gains to compute the base tax.

This feature is **informational only** — it does not affect any computed gains or cost
basis. It is activated on demand via a CLI flag so the output is not cluttered for
users who declared on time.

## CLI flags added

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--calculate-late-declaration-penalties` | `-cldp` | `store_true` | off | Activate the penalty calculation |
| `--penalty-scenario` | — | `choice` | `spontaneous` | `spontaneous` (10 %), `formal` (40 %), `fraud` (80 %) |
| `--declaration-deadline` | — | `YYYY-MM-DD` | June 1 of `target_year + 1` | Override the assumed original filing deadline |
| *(shorthand)* | `-s` | `store_true` | — | Alias for `-cldp --penalty-scenario spontaneous` |
| *(shorthand)* | `-f` | `store_true` | — | Alias for `-cldp --penalty-scenario formal` |
| *(shorthand)* | `-ff` | `store_true` | — | Alias for `-cldp --penalty-scenario fraud` |

Note: `-f` was previously the short alias for `--folder`; it was removed to free the flag for `-f` (formal).

## Computation logic

```
deadline         = --declaration-deadline  OR  date(target_year + 1, 6, 1)
months_delay     = ceil((today - deadline).days / 30.4375)   [0 if today ≤ deadline]

tax_owed         = net_gain_2074 × 0.30
late_interest    = tax_owed × 0.002 × months_delay
penalty_surcharge = tax_owed × penalty_rate   [0.10 / 0.40 / 0.80]
total_due        = tax_owed + late_interest + penalty_surcharge
```

Months are counted using ceiling division over 30.4375 days (average calendar month),
consistent with how the DGFiP counts full or partial months of delay.

## Output

The penalty block appears immediately after the Formulaire 2074 gains table in both
the console output and the generated `README.md`. One block is printed per year with
positive gains in `by_year_2074`. If a year has a loss or zero gain, a short message
notes that no penalty applies.

Example block (spontaneous scenario, 11 months delay, 500 € gain):

```
## Pénalités de déclaration tardive — Formulaire 2074 (2024)

> Scénario : correction spontanée avant mise en demeure · Délai : 11 mois
> (échéance : 2025-06-01, calcul au 2026-04-22)

| | Montant |
|---|---------|
| Plus-value nette | +500.00 € |
| Impôt dû (PFU 30 %) | 150.00 € |
| Intérêts de retard (0,20 % × 11 mois) | 3.30 € |
| Majoration (10 %) | 15.00 € |
| **Total estimé à régulariser** | **168.30 €** |

> ⚠ Estimation indicative — consultez votre SIP ou un conseiller fiscal.
```

## Scope

- Applies only to **Formulaire 2074** gains (securities). Formulaire 2086 (crypto-ETP
  informational output) and dividends are excluded.
- Does **not** cover the separate **Formulaire 3916** flat penalty (1 500 € for
  non-declaration of a foreign account) — that is a fixed amount unrelated to gains.
- Does **not** handle the case where a partial year of gains was already declared
  (correction of a partial omission). The calculation assumes the full `net_gain_2074`
  for the year was undeclared.

## Example usage

```bash
python src/yuh_csv_ifu.py 2024 -s                                      # spontaneous (10 %)
python src/yuh_csv_ifu.py 2024 -f                                      # formal notice (40 %)
python src/yuh_csv_ifu.py 2024 -ff                                     # fraud (80 %)
python src/yuh_csv_ifu.py 2024 -s --declaration-deadline 2025-05-15   # custom deadline
python src/yuh_csv_ifu.py 2024 -cldp --penalty-scenario spontaneous   # explicit long form
```

## Files modified

- `src/yuh_csv_ifu.py` — `import math`, three new `argparse` arguments, penalty
  computation block inserted after the 2074 gains table in `main()`
