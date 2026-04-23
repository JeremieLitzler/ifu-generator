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

## Why does the script say "PMP calculé sur X fichier(s) CSV" when I only asked for one year?

Because PMP requires the **full purchase history**, not just the target year. If you bought 10 shares in 2022, added 5 in 2023, and sold 8 in 2024, the correct cost basis for the 2024 sale depends on all the 2022 and 2023 buys. The script reads every `ACTIVITIES_REPORT-*.CSV` file in the transactions folder to build the complete history, then filters the output to the target year only.

---

## What exchange rate is used for CHF/USD → EUR conversion?

ECB (European Central Bank) rates fetched via `api.frankfurter.dev`. If a transaction falls on a weekend or public holiday, the last business day's rate is used — the standard DGFiP practice.

---

## Are broker commissions included in the cost basis?

Yes. For Yuh, the cost basis of a buy = `abs(DEBIT)`, which includes the Yuh commission. Auto-exchange fees (`BANK_AUTO_ORDER_EXECUTED`) are also added to the cost basis of the corresponding buy order, as they are *frais d'acquisition* under the PMP method.

---

## How are BANK_AUTO_ORDER_EXECUTED auto-exchange fees matched to a specific buy order?

The script matches each auto-exchange fee to a buy transaction using two criteria: (1) same date, and (2) same foreign currency (the exchange's `CREDIT CURRENCY` equals the buy's `DEBIT CURRENCY`). When exactly one buy satisfies both criteria, the CHF fee is converted to EUR at the BCE rate for that date and added to that transaction's `exchange_fee_eur` field, which flows into the PMP cost basis.

Amount-based matching is not used — the exchanged USD amount and the buy's USD debit are not expected to match exactly due to how Yuh books the two legs internally.

---

## What happens when an auto-exchange fee cannot be attributed to a specific buy?

It is reported in the "Frais d'autochange non attribués" section of the console summary and `README.md` with both its original CHF value and the BCE-converted EUR equivalent. A warning is printed if the ambiguity is caused by multiple buy orders in the same foreign currency on the same day. Truly unmatched fees (no buy found at all) are treated the same way.

---

## Does auto-exchange fee attribution apply to recurring invest orders?

Yes. Both `INVEST_ORDER_EXECUTED` and `INVEST_RECURRING_ORDER_EXECUTED` rows are treated as buy transactions for matching purposes. If a `BANK_AUTO_ORDER_EXECUTED` row on the same date shares the same foreign currency, the fee is attributed regardless of which invest activity type triggered it.

---

## Is there an audit trail for attributed auto-exchange fees in the output CSVs?

Yes. The `*_transactions.csv` output includes an `exchange_fee_eur` column showing the EUR-converted auto-exchange fee attributed to each buy transaction. A value of `0.0` means no fee was attributed — either the buy was in CHF (no auto-exchange needed) or the fee was ambiguous/unmatched and reported in the lump-sum section instead.

---

## Are Wise management fees deductible?

No — and this applies under **both** PFU and the barème progressif option.

Art. 150-0 D CGI defines the capital gain as `prix de cession − prix de revient`. The *prix de revient* can only include the acquisition price plus **frais d'acquisition** — fees paid *at the moment of buying* (brokerage commissions, transaction taxes). Wise's monthly platform fees are *frais de gestion courants* (ongoing management charges), not frais d'acquisition, so they cannot be added to the cost basis under either tax regime.

The historical deduction for *frais de garde* that existed before 2018 applied only to *revenus de capitaux mobiliers* (dividends, interest), not to capital gains — and was suppressed by the Finance Law 2017 alongside the introduction of PFU.

The fees are logged in `<year>_fees.csv` for records but have no impact on the computed gain.

---

## How are crypto-ETPs handled?

Crypto-ETPs (WisdomTree, CoinShares, ETC Group, etc.) are classified as **valeurs mobilières** and their gains go on **form 2074**, not form 2086. Legal basis: art. L. 54-10-1 CMF defines *actifs numériques* and explicitly excludes financial instruments (art. L. 211-1 CMF). Crypto-ETPs are admitted to trading on regulated markets (LSE, Xetra, Euronext), carry an ISIN, and are issued by regulated entities — so they fall outside the art. 150 VH bis CGI / form 2086 regime by statute (confirmed at BOI-RPPM-PVBMI-70-10-10 §20–30).

A precautionary `<year>_gains_2086.csv` is also produced in case the DGFiP ever issues a contrary ruling, but **do not file form 2086 for these instruments**. The list of crypto-ETP ISINs is maintained in `CRYPTO_ETP_ISINS` inside `src/yuh_csv_ifu.py` and must be updated when new ones are held.

---

## How are dividends classified between ligne 2DC and 2TR on form 2042?

The script derives the classification automatically from the ISIN:

- **ISIN prefix `FR`** → ligne **2DC** (eligible for the 40 % abatement under art. 158-3-2° CGI — French companies only)
- **All other prefixes** (IE, US, GB, CH, LU, DE, …) → ligne **2TR** (non-eligible)

This is already a maintained invariant since the ISIN is always present in `ticker_isin.py`. No manual classification is needed.

---

## How does the script determine whether foreign withholding tax (zone AA) applies to a dividend?

It maps the two-letter ISIN country prefix to one of three regimes via the `WITHHOLDING_REGIME` dict:

| Regime | Prefixes | Behaviour |
|--------|----------|-----------|
| `zero` | IE, LU, GB, FR | Output confirms zone AA = 0 € automatically |
| `treaty_recoverable` | US, CH | ⚠ per-ticker warning; manual entry of `withholding_tax_native` required from the Yuh *relevé fiscal annuel* |
| `unknown` | all others | ℹ advisory; check the applicable tax treaty |

The recovered withholding goes on **ligne 2AB** of form 2042.

---

## Why are Irish (IE) and Luxembourg (LU) ETF dividends shown as zero withholding?

Because the **fund domicile country** determines what is withheld at the investor level, not the country of the underlying holdings:

- **IE** — Ireland does not withhold tax on UCITS distributions paid to non-resident investors. This is the structural reason most European ETFs are domiciled in Ireland.
- **LU** — Luxembourg applies the same principle for UCITS funds.
- **GB** — The UK abolished dividend withholding tax entirely; distributions to non-residents are paid gross.
- **FR** — For a French tax resident, a French company's dividend is not "foreign withholding" — no foreign state takes a cut. Zone AA covers only tax withheld by a *foreign* country.

---

## What is zone DQ and how do I declare prélèvements sociaux on form 2042?

Zone DQ is the line the **broker** fills on the IFU to declare the social contributions base (montant brut des revenus distribués). Since Yuh does not withhold, the gross equals the net and `base_DQ_eur` in `<year>_dividendes.csv` equals the dividend amount.

For your **own form 2042** declaration:

- **Under PFU (default)**: the 17.2 % prélèvements sociaux are computed automatically by the DGFiP from the amounts you enter on lines 2TR / 2DC. No separate social contributions line to fill.
- **Under barème progressif** (opt-in): same 2TR / 2DC amounts. The CSG déductible portion (6.8 %) may additionally be reported on line **2CG**.

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

## Can I override the assumed declaration deadline when calculating penalties?

Yes — pass `--declaration-deadline YYYY-MM-DD` alongside `-s`/`-f`/`-ff` or `-cldp`. The default deadline is **June 1 of the year following the tax year** (e.g. `2025-06-01` for 2024 income). Override it if your specific deadline was earlier, for example the paper deadline in mid-May or an online deadline for an earlier fiscal zone.

```bash
python src/yuh_csv_ifu.py 2024 -s --declaration-deadline 2025-05-15
```

---

## Why was `-f` removed as the shorthand for `--folder`?

The `-f` flag was reassigned to mean "formal penalty scenario" (40 % surcharge) when the `-s`/`-f`/`-ff` penalty shortcuts were introduced. Use the long form `--folder` instead. The default (`transactions/`) is correct for most setups, so this only affects users who were explicitly passing `-f <path>` on the command line.

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

## Who is supposed to file the IFU 2561 — the broker or me?

The IFU 2561 is filed by the **établissement payeur** (the broker), not by the individual investor. It is a legal obligation under art. 242 ter CGI that applies only to French-domiciled payers.

Yuh/Swissquote and Wise are Swiss brokers — they are not subject to French tax reporting obligations and **do not file an IFU** on your behalf. You must declare your income yourself via form **2042** (dividends) and **2074** (capital gains).

This project generates the data that a French broker *would* have put in an IFU, so you can fill in your own tax return correctly.

---

## What is the IFU 2561 filing deadline?

**15 February** of the year following the income year (e.g. 15 February 2025 for 2024 income). A one-day administrative tolerance may push this to the following Monday.

This deadline applies to the établissement payeur (broker). For your personal tax return (form 2042), the deadline is the standard late May / early June deadline set each year by the DGFiP for online declarations.

---

## I hold only ETFs, no individual stocks. Does the 40 % abattement ever apply to my dividends?

No. The 40 % abattement (IFU zone AY / form 2042 ligne 2DC) applies exclusively to distributions from **companies** (*revenus distribués éligibles* under art. 158-3-2° CGI). ETF distributions are never eligible, regardless of how they are labelled by the broker.

With a 100 % ETF portfolio, all distributions go to **zone AZ / ligne 2TR** only. Zone AY stays zero and no split is needed.

---

## What is zone AN on the IFU 2561?

Zone AN is the **total gross proceeds** from all securities sales during the year, expressed in euros. It must be reported even if the net gain is zero or negative.

In the script output, compute it by summing `credit_eur` across all sell rows in `<year>_transactions.csv`.

---

## Can a script automatically fill in the IFU PDF forms?

No — the official PDFs (`2561_R24.pdf`, `2561_ter_R24.pdf`) are **flat, non-interactive** files with no fillable AcroForm fields. They are explicitly labelled *"Support visuel uniquement — Ne pas envoyer à la DGFiP"*.

The most practical alternative is a **summary report script** that reads the CSV outputs and prints each IFU zone value alongside the corresponding 2042 / 2074 line to type into the online declaration at impots.gouv.fr.

---

## Where are the official IFU PDF forms stored in this project?

In `tax_forms/<year>/`. For 2024 income:

| File | Content |
|------|---------|
| `tax_forms/2024/2561_NOT_R25_notice.pdf` | Explanatory notice (filing rules, field descriptions) |
| `tax_forms/2024/2561_R24.pdf` | Main form (zones AN, AY, AZ, AA, AD, …) |
| `tax_forms/2024/2561_ter_R24.pdf` | Tax credit certificate (zones 2AB, 2CK, capital gains summary) |

These files are for reference only and are not submitted to the DGFiP.

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
