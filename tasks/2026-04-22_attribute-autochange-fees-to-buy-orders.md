# Task: Attribute BANK_AUTO_ORDER_EXECUTED fees to individual buy orders

Created: 2026-04-22

## Problem

`BANK_AUTO_ORDER_EXECUTED` (CHF→USD/EUR auto-exchange) transactions carry a fee in
`FEES/COMMISSION` (in CHF). Currently the code collects these fees in `exchange_fees`
and reports them as an **informational lump sum** only — they are never added to the
cost basis (`total_cost_eur`) of the security that triggered the exchange.

This under-states acquisition costs, producing slightly inflated capital gains.

## Are these fees deductible?

Yes. Under the PMP method (art. 150-0 D CGI), *frais d'acquisition* are included in
the cost basis. An auto-exchange fee is a direct cost of acquiring the foreign currency
needed to fund a buy order; it is part of the total acquisition cost of that security.

The existing `INVEST_ORDER_EXECUTED` `FEES/COMMISSION` column already captures the
Yuh trading commission in the native currency. The auto-exchange fee is a separate,
additional CHF cost that must also be included.

## Nature of BANK_AUTO_ORDER_EXECUTED

`BANK_AUTO_ORDER_EXECUTED` is triggered **automatically by Yuh** as part of executing
an invest order in a non-CHF currency (e.g. USD). It is not a standalone user action —
it is the currency-conversion leg of the same investment operation.

Concretely for a USD buy:

| Row type                   | DEBIT      | CREDIT    |
|----------------------------|------------|-----------|
| `BANK_AUTO_ORDER_EXECUTED` | −X CHF     | +Y USD    |
| `INVEST_ORDER_EXECUTED`    | −Z USD     | —         |

The credit USD amount (Y) and the invest debit USD amount (Z) are **not expected to
match** — Y is the gross USD purchased; Z is the actual security cost net of how Yuh
internally books the transaction. Amount-based matching is **not a reliable strategy**.

## Matching strategy

Since the auto-exchange is always on the **same date** and in the **same foreign
currency** as the invest order it funds, match on:

1. **Same date** (`DATE` column).
2. **Currency match**: exchange `CREDIT CURRENCY` == invest `DEBIT CURRENCY`.

When there is exactly one exchange row and one invest buy row satisfying these criteria
on the same date, attribute the exchange fee to that invest order.

If there are multiple invest orders in the same currency on the same date, the fee
cannot be unambiguously attributed → treat as unattributed (current lump-sum behaviour)
and emit a warning.

## Proposed implementation

1. **During `parse_csv_file`**: collect `BANK_AUTO_ORDER_EXECUTED` rows as before.

2. **After parsing, before FX conversion**: for each exchange fee, find buy
   `Transaction` rows on the same date with the same `currency`. If exactly one match:
   - Convert `fee_chf` to EUR using the BCE rate for that date (CHF→EUR).
   - Store as a new field `exchange_fee_eur` on the matched `Transaction`.

3. **In `compute_gains`**: for buy transactions, add `exchange_fee_eur` to
   `total_cost_eur` alongside `tx.total_eur`.

4. **Unmatched fees**: keep the existing lump-sum warning/log, but also convert each
   unattributed fee to EUR (CHF→EUR BCE rate for that date) and report both the CHF
   and EUR values.

5. **Output**: include `exchange_fee_eur` column in `*_transactions.csv` for audit.

## Verification steps

- [ ] Inspect real CSV(s) to confirm date + currency is sufficient to uniquely identify
      the invest order for each auto-exchange row.
- [ ] Run the script on a sample year and compare `*_gains_2074.csv` before/after to
      confirm cost basis increased by the auto-exchange fees.
- [ ] Ensure `INVEST_RECURRING_ORDER_EXECUTED` rows are covered (they also trigger
      auto-exchanges).

## Files to modify

- [ ] `yuh_csv_ifu.py` — matching logic + updated cost basis
- [ ] `constants.py` — no change expected
- [ ] Task file to be closed once verified and merged
