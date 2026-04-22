#!/usr/bin/env python3
"""
unified_readme.py — Récapitulatif fiscal unifié Yuh + Wise pour une année donnée.

Lit les CSV produits par yuh_csv_ifu.py et wise_csv_ifu.py et produit
un tableau par formulaire avec les montants exacts à saisir en ligne.

Usage:
    python3 src/unified_readme.py <année> [--ifu-root <dossier>]
                                  [-s | -f | -ff | -cldp [--penalty-scenario ...] [--declaration-deadline YYYY-MM-DD]]

Prérequis :
    Avoir exécuté yuh_csv_ifu.py et/ou wise_csv_ifu.py au préalable.

Produit :
    ifu/<année>/README.md  — valeurs à saisir par formulaire (2074, 2042)
"""
import argparse
import csv
import math
import sys
from datetime import date, datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Lecture des CSV produits par les scripts broker
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def _f(s: str) -> float:
    try:
        return float(s.strip().replace('+', '').replace(' ', ''))
    except (ValueError, AttributeError):
        return 0.0


def sum_gains(rows: list[dict], col: str = 'Plus/moins-value EUR') -> float:
    return sum(_f(r[col]) for r in rows if col in r)


def sum_col(rows: list[dict], col: str) -> float:
    return sum(_f(r[col]) for r in rows if col in r)


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Récapitulatif fiscal unifié Yuh + Wise — valeurs à saisir par formulaire.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('year', type=int, help='Année fiscale cible (ex. 2024)')
    parser.add_argument('--ifu-root', default='ifu',
                        help="Dossier racine des sorties broker (défaut: 'ifu')")
    parser.add_argument('--calculate-late-declaration-penalties', '-cldp',
                        action='store_true')
    parser.add_argument('--penalty-scenario',
                        choices=['spontaneous', 'formal', 'fraud'],
                        default='spontaneous')
    parser.add_argument('--declaration-deadline', default=None, metavar='YYYY-MM-DD')
    parser.add_argument('-s', action='store_true', dest='penalty_s')
    parser.add_argument('-f', action='store_true', dest='penalty_f')
    parser.add_argument('-ff', action='store_true', dest='penalty_ff')
    args = parser.parse_args()

    if args.penalty_ff:
        args.calculate_late_declaration_penalties = True
        args.penalty_scenario = 'fraud'
    elif args.penalty_f:
        args.calculate_late_declaration_penalties = True
        args.penalty_scenario = 'formal'
    elif args.penalty_s:
        args.calculate_late_declaration_penalties = True
        args.penalty_scenario = 'spontaneous'

    year = args.year
    root = Path(args.ifu_root)

    yuh_dir  = root / str(year) / 'yuh'
    wise_dir = root / str(year) / 'wise'
    out_dir  = root / str(year)

    # --- Gains 2074 ---
    yuh_gains  = _read_csv(yuh_dir  / f'{year}_gains_2074.csv')
    wise_gains = _read_csv(wise_dir / f'{year}_gains_2074.csv')

    yuh_2074  = sum_gains(yuh_gains,  'Plus/moins-value EUR')
    wise_2074 = sum_gains(wise_gains, 'Plus/moins-value EUR (PMP)')
    total_2074 = yuh_2074 + wise_2074

    # --- Gains 2086 (informatif Yuh uniquement) ---
    yuh_gains_2086 = _read_csv(yuh_dir / f'{year}_gains_2086.csv')
    yuh_2086 = sum_gains(yuh_gains_2086, 'Plus/moins-value EUR')
    yuh_2086_proceeds = sum_col(yuh_gains_2086, 'Prix de cession EUR')

    # --- Dividendes 2042 (Yuh uniquement — Wise fonds capitalisants) ---
    yuh_divs = _read_csv(yuh_dir / f'{year}_dividendes.csv')
    divs_2dc = [r for r in yuh_divs if '2DC' in r.get('Ligne 2042', '')]
    divs_2tr = [r for r in yuh_divs if '2TR' in r.get('Ligne 2042', '')]
    total_2dc = sum_col(divs_2dc, 'Montant EUR')
    total_2tr = sum_col(divs_2tr, 'Montant EUR')
    total_2ab = sum_col(yuh_divs, 'Retenue à la source EUR (zone AA)')

    # --- Frais Wise (informatif) ---
    wise_fees = _read_csv(wise_dir / f'{year}_fees.csv')
    total_fees = sum_col(wise_fees, 'Montant EUR')

    # Détermination des sources disponibles
    sources = []
    if yuh_gains or yuh_divs:
        sources.append('Yuh')
    if wise_gains or wise_fees:
        sources.append('Wise')

    if not sources:
        print(
            f"Aucune donnée trouvée pour {year}.\n"
            f"Attendu dans : {yuh_dir}  et/ou  {wise_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n📋 Sources : {', '.join(sources)}")

    # ===================================================================
    # Construction du README
    # ===================================================================

    md: list[str] = []

    def h(text: str) -> None:
        print(text)
        md.append(text)

    today = datetime.now().strftime('%Y-%m-%d')
    h(f"# Déclaration fiscale {year} — Valeurs à saisir")
    h(f"\n> Généré le {today} · Sources : {', '.join(sources)}\n")

    # --- Formulaire 2074 ---
    h("## Formulaire 2074 — Plus/moins-values valeurs mobilières\n")

    if yuh_gains or wise_gains:
        yuh_label  = f"{yuh_2074:+.2f} €"  if yuh_gains  else "—"
        wise_label = f"{wise_2074:+.2f} €" if wise_gains else "—"
        rounded = round(total_2074)
        box = "**3VG**" if rounded >= 0 else "**3VH**"
        h("| Source | Gain/perte EUR |")
        h("|--------|---------------|")
        if yuh_gains:
            h(f"| Yuh | {yuh_label} |")
        if wise_gains:
            h(f"| Wise | {wise_label} |")
        h(f"| **Total** | **{total_2074:+.2f} €** |")
        h(f"\n→ Saisir **{rounded:+d} €** en case {box}")
        if rounded >= 0:
            h("\n> Plus-value : case **3VG** du formulaire 2074 (et 2042 C ligne 3VG).")
        else:
            h("\n> Moins-value : case **3VH** du formulaire 2074 (imputable sur gains futurs).")
    else:
        h(f"Aucune cession en {year} — rien à déclarer.")

    if args.calculate_late_declaration_penalties and (yuh_gains or wise_gains) and total_2074 > 0:
        _RATES = {
            'spontaneous': (0.10, "correction spontanée avant mise en demeure"),
            'formal':      (0.40, "après mise en demeure"),
            'fraud':       (0.80, "manœuvres frauduleuses"),
        }
        penalty_rate, scenario_label = _RATES[args.penalty_scenario]
        if args.declaration_deadline:
            deadline = datetime.strptime(args.declaration_deadline, '%Y-%m-%d').date()
        else:
            deadline = date(year + 1, 6, 1)
        today_date = date.today()
        months_delay = (
            math.ceil((today_date - deadline).days / 30.4375) if today_date > deadline else 0
        )
        tax_owed = round(rounded * 0.30)  # rounded = round(total_2074), already computed above
        late_interest = round(tax_owed * 0.002 * months_delay)
        surcharge = round(tax_owed * penalty_rate)
        total_due = tax_owed + late_interest + surcharge

        h(f"\n## Pénalités de déclaration tardive — Formulaire 2074\n")
        h(f"> Scénario : **{scenario_label}** · "
          f"Délai : **{months_delay} mois** "
          f"(échéance : {deadline.isoformat()}, calcul au {today_date.isoformat()})\n")
        h("| | Montant |")
        h("|---|---------|")
        h(f"| Plus-value nette (arrondie, case 3VG) | {rounded:+d} € |")
        h(f"| Impôt dû (PFU 30 %) | {tax_owed} € |")
        h(f"| Intérêts de retard (0,20 % × {months_delay} mois) | {late_interest} € |")
        h(f"| Majoration ({penalty_rate * 100:.0f} %) | {surcharge} € |")
        h(f"| **Total estimé à régulariser** | **{total_due} €** |\n")
        h("> ⚠ Estimation indicative — consultez votre Service des Impôts des Particuliers (SIP) ou un conseiller fiscal.")

    # --- Formulaire 2086 informatif ---
    if yuh_gains_2086:
        h("\n## Formulaire 2086 — ⚠ Informatif seulement (crypto-ETPs Yuh)\n")
        rounded_2086 = round(yuh_2086)
        box_2086 = "3AN" if rounded_2086 >= 0 else "3BN"
        h("| | Valeur |")
        h("|---|-------|")
        h(f"| Plus/moins-value | {yuh_2086:+.2f} € |")
        h(f"| Cessions totales | {yuh_2086_proceeds:.2f} € |")
        if yuh_2086_proceeds <= 305.0:
            h(f"\n→ Cessions ≤ 305 € → **EXONÉRÉ** — rien à saisir.")
        else:
            h(f"\n→ Saisir **{rounded_2086:+d} €** en case **{box_2086}** si la DGFiP requalifie en actifs numériques.")
        h("\n> Classification retenue : valeurs mobilières (form. 2074). "
          "Ce bloc est produit à titre précautionnel uniquement.")

    # --- Formulaire 2042 — Dividendes ---
    h("\n## Formulaire 2042 — Dividendes / Distributions\n")

    if yuh_divs:
        h("| Case | Description | Montant EUR | Arrondi | À saisir |")
        h("|------|-------------|------------|---------|----------|")
        if divs_2dc:
            h(f"| **2DC** | Distributions éligibles abattement 40 % (ISIN FR) "
              f"| {total_2dc:.2f} | {round(total_2dc):+d} € | ✓ |")
        if divs_2tr:
            h(f"| **2TR** | Distributions non éligibles (étrangères) "
              f"| {total_2tr:.2f} | {round(total_2tr):+d} € | ✓ |")
        if total_2ab > 0:
            h(f"| **2AB** | Retenue à la source étrangère (zone AA) "
              f"| {total_2ab:.2f} | {round(total_2ab):+d} € | ✓ |")
        else:
            h("| **2AB** | Retenue à la source (zone AA) | 0.00 | 0 € | — (néant) |")
        h(f"\n> Base prélèvements sociaux (zone DQ) : **{round(total_2dc + total_2tr):+d} €**")
    else:
        h("Aucun dividende Yuh pour cette année.")

    if wise_fees:
        h("\n> Wise Assets : fonds capitalisants — aucune distribution à déclarer.")

    # --- Frais Wise informatifs ---
    if wise_fees:
        h(f"\n## Frais de gestion Wise — informatif\n")
        h(f"Total {year} : **{total_fees:.2f} EUR** — "
          f"non déductibles (art. 150-0 D CGI), aucune saisie requise.")

    # --- Formulaire 3916 ---
    h("\n## Formulaire 3916 — Comptes étrangers\n")
    accounts = []
    if 'Yuh' in sources:
        accounts.append("Yuh / Swissquote (Suisse)")
    if 'Wise' in sources:
        accounts.append("Wise (Belgique)")
    for acc in accounts:
        h(f"- [ ] Déclarer le compte **{acc}**")
    h("\n> 1 500 € d'amende par compte non déclaré.")

    # --- Rappels ---
    h("\n## Rappels\n")
    h("- **ETFs capitalisants** : imposition uniquement à la cession.")
    h("- **Méthode PMP** : les montants ci-dessus sont calculés selon l'art. 150-0 D CGI. "
      "Le relevé fiscal annuel Wise utilise FIFO — les montants peuvent différer.")
    h(f"- **Conserver les CSV 10 ans** (durée de reprise fiscale).")

    # --- Écriture ---
    out_dir.mkdir(parents=True, exist_ok=True)
    out_readme = out_dir / 'README.md'
    out_readme.write_text('\n'.join(md), encoding='utf-8')
    print(f"\n📝 Récapitulatif          → {out_readme}\n")


if __name__ == '__main__':
    main()
