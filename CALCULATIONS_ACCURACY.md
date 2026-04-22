# Calculations Accuracy

Honest assessment by area of the computations performed by `src/yuh_csv_ifu.py`,
`src/wise_csv_ifu.py`, and `src/unified_readme.py`.

## High confidence

- **PMP formula** — the weighted average cost logic (art. 150-0 D CGI) is standard
  and the code handles buys, sells, and position zeroing correctly.
- **FX conversion** — ECB rates via frankfurter.dev with weekend/holiday fallback is
  the standard DGFiP-accepted method.
- **Penalty rates** — 10 %/40 %/80 % surcharges and 0.20 %/month interest are correct
  per art. 1728 and 1727 CGI.

## Medium confidence — known simplifications

- **Months delay** — `ceil(days / 30.4375)` approximates calendar months. The DGFiP
  counts actual calendar months (partial month = full month). Could be off by ±1 month
  near month boundaries.
- **Auto-exchange fee attribution** — matched by date + currency. If two buys happen on
  the same day in the same currency, the fee is left unattributed. Edge case, but possible.

## Lower confidence — deliberate assumptions that may not apply to your situation

- **2DC vs 2TR classification** — based purely on ISIN prefix (`FR` → 2DC). The actual
  40 % abattement eligibility requires the company to be subject to French or EU corporate
  tax, which the ISIN prefix alone does not guarantee. Needs verification against the
  fund's prospectus.
- **Crypto-ETP as valeurs mobilières** — legally defensible (art. L.54-10-1 CMF) but
  the DGFiP has not issued a formal ruling. The 2086 informational output exists precisely
  for this uncertainty.
- **Wise management fees as non-deductible** — correct under PFU; under barème progressif
  the answer is more nuanced and contested.

## Bottom line

The numbers are a solid starting point and the methodology is sound, but verify the 2DC
eligibility for each fund and treat the penalty total as an estimate (±1 month, rounding).
For significant amounts, confirm with a conseiller fiscal or your Service des Impôts des
Particuliers (SIP).
