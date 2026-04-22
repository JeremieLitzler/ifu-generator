# Fix: IFU 2561-NOT compliance gaps in yuh_csv_ifu.py

Created: 2026-04-22
Reference: review against notice N°2561-NOT (N°50673#26, revenus 2024)

## Context

`src/yuh_csv_ifu.py` reconstructs the IFU-equivalent data that Yuh (Swiss broker) does
not provide to the DGFiP. A compliance review against notice N°2561-NOT (revenus 2024, filed in 2025) identified
four gaps. **These fixes target the `2024` target year only**; rules for revenus 2025
should be re-reviewed against the applicable notice before implementing changes for that
year. Two require code changes; two are primarily documentation/output improvements.
All fixes are **informational only** — they do not affect PMP calculations or gain/loss
figures.

---

## Issue 1 — Foreign withholding tax not tracked (zone AA)

Zone AA of form 2561 records the foreign tax credit (_crédit d'impôt conventionnel_)
available when a tax treaty between France and the source country authorises imputing
the foreign withholding against French income tax (art. 78 annexe II CGI). For Yuh
users this is relevant for: US stock dividends (15 % or 30 % withholding, recoverable
under the France–US treaty at up to 15 %), and Swiss equity dividends (35 % _impôt
anticipé_). **The Yuh CSV records only the net credit amount after withholding; the
gross pre-withholding amount and the amount withheld are not present in the CSV.**
This means the script cannot compute zone AA automatically.

**Code change needed**: add a `withholding_tax_native` field to `Transaction` and a
corresponding `withholding_tax_eur` output column to `*_dividendes.csv`. Default both
to `0.0`. Populate them from a future data source if one becomes available.

**Regime classification**: a `WITHHOLDING_REGIME` dict in the script maps the two-letter
ISIN country prefix to one of three regimes:

- `zero` — confirmed 0 % for non-resident investors; no manual step required:
  - **IE** — Irish UCITS ETFs distribute without withholding to non-residents under
    Irish domestic law. This is the structural reason most European ETFs are domiciled
    in Ireland.
  - **LU** — Luxembourg UCITS funds apply the same principle.
  - **GB** — The UK abolished dividend withholding tax entirely; distributions to
    non-residents are paid gross regardless of treaty.
  - **FR** — For a French tax resident, a French company's dividend is not "foreign
    withholding" — no foreign state takes a cut. Zone AA is specifically for tax
    withheld by a _foreign_ country.
- `treaty_recoverable` — withholding is likely; manual entry of `withholding_tax_native`
  required:
  - **US** — 15–30 % NRA withholding; France–US treaty caps recovery at 15 %.
  - **CH** — 35 % _impôt anticipé_ (Verrechnungssteuer).
- `unknown` — all other prefixes; treaty situation unclear, advisory note shown.

At runtime, if any dividend row has a `treaty_recoverable` prefix and
`withholding_tax_eur == 0`, the console/README emits a per-ticker ⚠ warning instructing
the user to consult the Yuh _relevé fiscal annuel_ and fill in `withholding_tax_native`
manually before re-running the script. For `unknown` prefixes an advisory is shown.
If all dividends are from `zero`-regime ISINs, the output confirms zone AA = 0 €
automatically. The recovered amount goes on line **2AB** (crédit d'impôt sur valeurs
étrangères) of form 2042, not on form 2074.

**Risk when historical documents are unavailable**: Yuh account
statements and portfolio performance PDFs are only available for one year after
issuance. The risk of not having them is **zero** for any year in which all
dividend-paying instruments have `zero`-regime ISINs (IE, LU, GB, FR), since the
script already confirms withholding = 0 € from the ISIN prefix alone — the documents
would add nothing.

The risk becomes real only in a year where instruments with
`treaty_recoverable` ISINs (US or CH) pay dividends, because those documents are the
only source for the gross amount and the withheld sum. In that situation, retrieve the
documents before they expire.

---

## Issue 2 — Dividend eligibility not classified (zone AY vs AZ / line 2DC vs 2TR)

The IFU distinguishes distributions eligible for the 40 % abatement (_zone AY → ligne
2DC_ of form 2042) from those that are not (_zone AZ → ligne 2TR_). The 40 % abatement
applies only to dividends from French companies (art. 158-3-2° CGI) and a small list
of EEA equivalents. Foreign-domiciled securities — which is the entire Yuh universe for
most users — produce distributions that are **not eligible** and must go on line 2TR.
Currently the script outputs `'2042 (revenus de capitaux mobiliers)'` for all dividends
without specifying the line.

**Code change needed**: add a `ligne_2042` column to `*_dividendes.csv`. Derive the
value automatically: if the ISIN country prefix is `FR`, emit `2DC (eligible abattement
40 %)`; for all other prefixes (IE, US, GB, CH, DE, …) emit `2TR (non eligible)`. The
`TICKER_ISIN` dict already contains the ISIN so no new data is required. Also update
the console summary header from `## Dividendes / Distributions — case 2DC ou 2TR` to
split the total by line.

**No manual step required** provided the ISIN in `ticker_isin.py` is correct, which is
already a maintained invariant of the project.

---

## Issue 3 — Zone DQ (social contributions base) not computed

For French tax residents, art. 117 quater and 125 A CGI require the gross amount of
dividends and fixed-income products to also be reported in **zone DQ** of form 2561,
which serves as the base for _prélèvements sociaux_ (17.2 %). The current output makes
no reference to zone DQ, leaving the user to infer this obligation.

Zone DQ is what the broker fills on the IFU. For the taxpayer's form 2042:
- Under **PFU (default)**: the 17.2 % prélèvements sociaux are computed automatically
  from the amounts declared on lines 2TR / 2DC — no separate PS line to fill.
- Under **barème progressif** (opt-in): same 2TR / 2DC amounts; the CSG déductible
  portion (6.8 %) may be reported on line **2CG**.

**Code change needed**: add a `base_DQ_eur` column to `*_dividendes.csv` equal to
`total_eur` for each dividend row (gross = net since Yuh does not withhold). In the
console/README summary, add a note explaining the DQ base and the correct form 2042
treatment under PFU vs. barème progressif.

**No manual step required** because Yuh does not withhold, so gross equals net. If
issue 1 is also fixed and a non-zero `withholding_tax_eur` is recorded, then
`base_DQ_eur` must be set to `total_eur + withholding_tax_eur` (the pre-withholding
gross).

---

## Issue 4 — Crypto-ETP 2074 classification caveat not surfaced with legal basis

The script classifies crypto-ETPs (WisdomTree Physical Bitcoin, CoinShares Physical
Bitcoin, etc.) as _valeurs mobilières_ and routes them to form 2074, with a
precautionary 2086 output. This classification is **legally correct** but the rationale
is not stated in the output, which may leave users uncertain. The legal basis is:

**Art. L. 54-10-1 du Code monétaire et financier** defines _actifs numériques_ and
explicitly **excludes** from that definition any instrument that qualifies as an
_instrument financier_ under **art. L. 211-1 du CMF**: _"Les actifs numériques
comprennent […] à l'exclusion de ceux qui ont les caractéristiques des instruments
financiers mentionnés à l'article L. 211-1 du présent code."_ Crypto-ETPs issued by
WisdomTree, CoinShares, ETC Group and similar issuers are **valeurs mobilières** per
L. 211-1 CMF — they are admitted to trading on regulated markets (London Stock
Exchange, Xetra, Euronext), carry an ISIN, and are issued by regulated entities. They
therefore fall **outside** the art. 150 VH bis CGI / form 2086 regime by statutory
definition. The BOFIP confirms the scope at **BOI-RPPM-PVBMI-70-10-10** (§ 20–30):
actifs numériques subject to art. 150 VH bis are those defined at L. 54-10-1 CMF,
which as shown above excludes financial instruments. The DGFiP had not issued a contrary ruling specific to crypto-ETPs as of the 2024
tax year; this should be re-verified before applying the same logic to subsequent
years.

**Code change needed**: in the console/README output, replace the bare `⚠ informatif`
note on the 2086 line with an expanded disclaimer that:
(a) states the 2074 classification is grounded in art. L. 54-10-1 CMF (exclusion of
financial instruments from the _actifs numériques_ definition);
(b) notes that a DGFiP requalification remains theoretically possible in the absence of
an explicit ruling, which is why the 2086 file is still produced;
(c) recommends consulting a _conseiller fiscal_ if the user holds large positions.
No structural logic change is needed — the existing 2074/2086 split is already correct.

**No manual step required.**
