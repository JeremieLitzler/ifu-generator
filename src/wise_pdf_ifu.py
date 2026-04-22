#!/usr/bin/env python3
"""
wise_pdf_ifu.py — Calcule l'équivalent d'un IFU à partir des relevés fiscaux PDF Wise
pour la déclaration fiscale française (résident fiscal français, frontalier).

Usage:
    python3 src/wise_pdf_ifu.py <année> [--folder <dossier>] [--cache <fichier_fx>]

Produit (préfixe par défaut : ifu_wise/<année>/) :
    - <année>_transactions.csv  : toutes les opérations de l'année
    - <année>_gains_2074.csv    : plus/moins-values (formulaire 2074)
    - <année>_dividendes.csv    : dividendes / distributions (vide pour fonds capitalisants)
    - <année>_fees.csv          : frais de gestion mensuels (non déductibles en PFU)
    - <année>_summary.csv       : positions et PMP au 31/12 de l'année cible
    - <année>_fx_log.csv        : journal des taux BCE utilisés

Hypothèses :
    - Input : relevés fiscaux annuels PDF Wise (wise_tax_statement_*.pdf).
    - Wise calcule en FIFO ; ce script RECOMPUTE en PMP (art. 150-0 D CGI).
    - Taux de change : BCE via api.frankfurter.dev. En 2024, tout est en EUR (taux=1).
    - Frais de gestion mensuels (Section III) : journalisés séparément, NON inclus dans
      le prix de revient (pas des frais d'acquisition au sens de l'art. 150-0 D CGI).
    - LIMITATION : le PDF Wise n'inclut que les achats appariés FIFO aux ventes de l'année.
      Les positions non cédées au 31/12 n'apparaissent PAS dans le PDF.
      Pour un PMP correct sur plusieurs années, passer TOUS les PDF disponibles.

Dépendances :
    pip install pdfplumber requests
"""
import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import pdfplumber
except ImportError:
    print("Dépendance manquante : pip install pdfplumber", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Dépendance manquante : pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Fonds Wise connus (ISIN → nom canonique)
# Ajouter tout nouveau fonds ici.
# ---------------------------------------------------------------------------
WISE_FUNDS: dict[str, str] = {
    'IE00B41N0724': 'EUR Interest fund',  # BlackRock ICS EUR Liquidity Fund (Irlande)
    'LU0852473015': 'Stocks fund',        # iShares World Equity Index Fund MSCI World (Luxembourg)
}

# Pas de crypto-ETPs chez Wise Assets → pas de formulaire 2086 nécessaire.


# ---------------------------------------------------------------------------
# Cache BCE multi-devises
# ---------------------------------------------------------------------------
class FXCache:
    """Cache persistant des taux {currency}→EUR BCE via api.frankfurter.dev."""

    API = "https://api.frankfurter.dev/v1/{date}?from={currency}&to=EUR"

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.cache: dict = {}
        if cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text())
            except Exception:
                self.cache = {}

    def _save(self):
        self.cache_path.write_text(json.dumps(self.cache, indent=2, sort_keys=True))

    def get(self, d: date, currency: str = 'EUR') -> tuple[float, str]:
        """Retourne (taux→EUR, date_BCE_réelle). Retourne (1.0, date) pour EUR."""
        if currency == 'EUR':
            return 1.0, d.isoformat()
        key = f"{d.isoformat()}_{currency}"
        if key in self.cache:
            e = self.cache[key]
            return e['rate'], e['bce_date']
        url = self.API.format(date=d.isoformat(), currency=currency)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        payload = r.json()
        if 'rates' not in payload or 'EUR' not in payload['rates']:
            raise RuntimeError(f"Réponse inattendue pour {key}: {payload}")
        rate = float(payload['rates']['EUR'])
        bce_date = payload.get('date', d.isoformat())
        self.cache[key] = {'rate': rate, 'bce_date': bce_date}
        self._save()
        return rate, bce_date


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------
@dataclass
class WiseTx:
    row_id: str
    date: date
    type: str            # 'buy' | 'sell'
    isin: str
    fund_name: str
    country: str
    quantity: float      # positif pour achat, négatif pour vente (comme dans le PDF)
    price_native: float  # prix unitaire (valeur absolue)
    fee_native: float    # frais de transaction (0,00 pour Wise)
    total_native: float  # montant en devise native (négatif achat, positif vente)
    currency: str
    accrued_interest: float
    withholding_native: float  # retenue à la source (0,00 confirmé)
    fx_rate: float       # taux de change vers EUR (1,0000 pour EUR)
    total_eur: float     # montant EUR (négatif achat, positif vente) — clé pour PMP
    fee_eur: float       # frais EUR (0,00 pour Wise)


@dataclass
class WiseFee:
    date: date
    currency: str
    quantity: float
    total_native: float  # toujours négatif
    fx_rate: float
    total_eur: float     # toujours négatif


# ---------------------------------------------------------------------------
# Parsing PDF
# ---------------------------------------------------------------------------

# Nombre en format européen : "1 234,56" ou "-100,00" ou "0,985325"
_N = r'-?[\d ]+,\d+'

# Ligne de transaction Section II : type + date + devise + 9 champs numériques
# Champs : qty | prix | frais_tx | [tx/accrued] | total_dev | wtax | fx | total_eur | frais_eur
_TX_RE = re.compile(
    r'^(Achat|Vente)\s+'
    r'(\d{2}\.\d{2}\.\d{4})\s+'
    r'([A-Z]{3})\s+'
    + r'\s+'.join([rf'({_N})'] * 9)
    + r'\s*$'
)

# En-tête ISIN dans Section II : "IE00B41N0724 - EUR Interest fund"
_ISIN_RE = re.compile(r'^([A-Z]{2}[A-Z0-9]{10})\s*-\s*(.+)$')

# Ligne Gains/Pertes (résultat FIFO Wise, ignoré pour PMP)
_GP_RE = re.compile(r'^Gains/Pertes\s+(' + _N + r')\s*$')

# Ligne de frais Section III : type + date + devise + 4 champs numériques
# Champs : qty | total_dev | fx | total_eur
_FEE_RE = re.compile(
    r'^Frais\s+'
    r'(\d{2}\.\d{2}\.\d{4})\s+'
    r'([A-Z]{3})\s+'
    + r'\s+'.join([rf'({_N})'] * 4)
    + r'\s*$'
)

# Noms de pays utilisés comme séparateurs de sous-section
_COUNTRIES = {
    'Irlande', 'Luxembourg', 'France', 'Allemagne',
    'Royaume-Uni', 'États-Unis', 'Suisse', 'Belgique',
}

# Lignes d'en-tête à ignorer
_HEADER_TOKENS = {
    'ISIN- N° de valeur- Nom', 'Transaction', 'valeur', 'Fonds',
    'Montant en Devise', 'Montant en EUR', 'Quantité / Nominal',
    'Prix unitaire', 'Frais de', 'transaction', 'Total Accrued',
    'Grande total en', 'Total des Frais',
}


def _n(s: str) -> float:
    """Parse European number : '1 234,56' → 1234.56"""
    return float(s.strip().replace('\xa0', '').replace(' ', '').replace(',', '.'))


def parse_wise_pdf(pdf_path: Path) -> tuple[list[WiseTx], list[WiseFee]]:
    """
    Parse un relevé fiscal annuel Wise.
    Retourne (transactions, frais_gestion).

    L'algorithme suit un automate d'états :
      - hors section → recherche "II. Gain en capital" ou "III. Autres Opérations"
      - section II   → suit les en-têtes ISIN/pays, parse Achat/Vente
      - section III  → parse les lignes Frais
    """
    transactions: list[WiseTx] = []
    fees: list[WiseFee] = []

    in_s2 = False   # Section II (gains en capital)
    in_s3 = False   # Section III (autres opérations / frais)
    current_isin = ''
    current_fund = ''
    current_country = ''
    row_counter = 0
    unmatched_lines: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ''
            for raw_line in text.split('\n'):
                line = raw_line.strip()
                if not line:
                    continue

                # ---- Détection des sections ----
                if re.search(r'II\.\s*Gain en capital', line):
                    in_s2, in_s3 = True, False
                    continue
                if re.search(r'III\.\s*Autres', line):
                    in_s2, in_s3 = False, True
                    continue
                if re.match(r'^IV\.', line):
                    in_s2, in_s3 = False, False
                    continue

                # ---- Lignes à ignorer partout ----
                if any(tok in line for tok in _HEADER_TOKENS):
                    continue
                if re.match(r'^Report ID', line) or 'Relation bancaire' in line:
                    continue
                if re.match(r'^Période', line) or re.match(r'^Devise', line):
                    continue

                # ---- Section II ----
                if in_s2:
                    # Pays (sous-section)
                    if line in _COUNTRIES:
                        current_country = line
                        continue

                    # En-tête ISIN
                    m = _ISIN_RE.match(line)
                    if m:
                        current_isin = m.group(1)
                        current_fund = m.group(2).strip()
                        if current_isin not in WISE_FUNDS:
                            print(f"  ⚠ ISIN inconnu : {current_isin} — ajoutez-le dans WISE_FUNDS",
                                  file=sys.stderr)
                        continue

                    # Gains/Pertes FIFO — ignoré (on recompute PMP)
                    if _GP_RE.match(line):
                        continue

                    # Ligne Achat / Vente
                    m = _TX_RE.match(line)
                    if m:
                        tx_str, date_str, devise = m.group(1), m.group(2), m.group(3)
                        qty, prix, frais_tx, tx_amt, total_dev, wtax, fx, total_eur, fee_eur = \
                            [_n(m.group(i)) for i in range(4, 13)]

                        tx_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                        tx_type = 'buy' if tx_str == 'Achat' else 'sell'
                        row_counter += 1

                        label = '✓' if tx_type == 'buy' else '↩'
                        print(f"  {label} {tx_date} {tx_type:4s} {current_isin} "
                              f"{(current_fund or WISE_FUNDS.get(current_isin, '?'))[:28]:28s} "
                              f"{qty:>12.6f} × {abs(prix):>8.4f} {devise}  → {total_eur:>9.2f} EUR")

                        transactions.append(WiseTx(
                            row_id=f"{tx_date.isoformat()}_{current_isin}_{tx_type}_{row_counter}",
                            date=tx_date,
                            type=tx_type,
                            isin=current_isin,
                            fund_name=current_fund or WISE_FUNDS.get(current_isin, current_isin),
                            country=current_country,
                            quantity=qty,
                            price_native=abs(prix),
                            fee_native=frais_tx,
                            total_native=total_dev,
                            currency=devise,
                            accrued_interest=tx_amt,
                            withholding_native=wtax,
                            fx_rate=fx,
                            total_eur=total_eur,
                            fee_eur=fee_eur,
                        ))
                        continue

                    # Lignes non reconnues en Section II
                    if line not in ('', 'Fonds') and not line.startswith('Page '):
                        unmatched_lines.append(f"S2: {line!r}")

                # ---- Section III ----
                elif in_s3:
                    m = _FEE_RE.match(line)
                    if m:
                        date_str, devise = m.group(1), m.group(2)
                        qty, total_dev, fx, total_eur = [_n(m.group(i)) for i in range(3, 7)]
                        fee_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                        fees.append(WiseFee(
                            date=fee_date,
                            currency=devise,
                            quantity=qty,
                            total_native=total_dev,
                            fx_rate=fx,
                            total_eur=total_eur,
                        ))
                        print(f"  💳 {fee_date} frais  {total_dev:>7.2f} {devise}")
                        continue

                    if line not in ('Frais',) and not line.startswith('Page ') \
                            and line not in _COUNTRIES:
                        unmatched_lines.append(f"S3: {line!r}")

    if unmatched_lines:
        print(f"\n  ℹ {len(unmatched_lines)} ligne(s) non reconnues (à vérifier) :",
              file=sys.stderr)
        for ul in unmatched_lines[:10]:
            print(f"    {ul}", file=sys.stderr)
        if len(unmatched_lines) > 10:
            print(f"    … et {len(unmatched_lines) - 10} de plus", file=sys.stderr)

    return transactions, fees


# ---------------------------------------------------------------------------
# Calcul des plus-values (PMP, art. 150-0 D CGI)
# ---------------------------------------------------------------------------
def compute_pmp_gains(txs: list[WiseTx]) -> dict:
    """
    Recalcule les plus/moins-values selon la méthode PMP sur l'ensemble de l'historique.
    Les transactions doivent couvrir TOUS les achats (tous les PDF disponibles)
    pour un PMP exact.
    """
    txs_sorted = sorted(txs, key=lambda t: (t.date, t.row_id))
    positions: dict[str, dict] = {}

    for tx in txs_sorted:
        p = positions.setdefault(tx.isin, {
            'name': tx.fund_name,
            'country': tx.country,
            'quantity': 0.0,
            'total_cost_eur': 0.0,
            'realized_gains': [],
        })

        if tx.type == 'buy':
            # Coût = abs(total_eur) + frais éventuels (fee_eur = 0 pour Wise)
            cost_eur = abs(tx.total_eur) + tx.fee_eur
            p['quantity'] += tx.quantity
            p['total_cost_eur'] += cost_eur

        elif tx.type == 'sell':
            qty_sold = abs(tx.quantity)
            if p['quantity'] <= 0 or p['quantity'] < qty_sold - 1e-6:
                print(f"  ⚠ Vente sans position suffisante pour {tx.isin} le {tx.date} "
                      f"(position={p['quantity']:.6f}, vendu={qty_sold:.6f})",
                      file=sys.stderr)
                continue
            pmp = p['total_cost_eur'] / p['quantity']
            cost_basis = pmp * qty_sold
            proceeds = tx.total_eur   # positif pour une vente
            gain = proceeds - cost_basis

            p['realized_gains'].append({
                'date': tx.date.isoformat(),
                'row_id': tx.row_id,
                'quantity': qty_sold,
                'proceeds_eur': proceeds,
                'cost_basis_eur': cost_basis,
                'pmp_eur': pmp,
                'gain_eur': gain,
            })
            p['quantity'] -= qty_sold
            p['total_cost_eur'] -= cost_basis
            if abs(p['quantity']) < 1e-9:
                p['quantity'] = 0.0
                p['total_cost_eur'] = 0.0

    return positions


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="IFU Wise — recompute PMP from annual tax PDF (French resident)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('year', type=int, help='Année fiscale cible (ex. 2024)')
    parser.add_argument('--folder', default='transactions',
                        help="Dossier contenant les PDF Wise (défaut: 'transactions')")
    parser.add_argument('--cache', default='fx_cache.json',
                        help="Fichier cache des taux BCE (défaut: fx_cache.json)")
    args = parser.parse_args()

    target_year = args.year
    folder = Path(args.folder)
    out_dir = Path('ifu') / 'wise' / str(target_year)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not folder.is_dir():
        print(f"Dossier introuvable : {folder}", file=sys.stderr)
        sys.exit(1)

    # Tous les PDF Wise disponibles (tous les ans pour un PMP correct)
    all_pdfs = sorted(folder.glob('wise_tax_statement_*.pdf'))
    if not all_pdfs:
        print(f"Aucun fichier wise_tax_statement_*.pdf trouvé dans {folder}",
              file=sys.stderr)
        sys.exit(1)

    # PDF de l'année cible (obligatoire)
    target_pdfs = [p for p in all_pdfs
                   if str(target_year) in p.stem]
    if not target_pdfs:
        print(f"Aucun PDF Wise pour l'année {target_year} dans {folder}",
              file=sys.stderr)
        sys.exit(1)

    # --- Parsing de tous les PDF (pour PMP correct) ---
    all_txs: list[WiseTx] = []
    all_fees: list[WiseFee] = []

    for pdf_path in all_pdfs:
        print(f"\n📄 Lecture {pdf_path.name} ...")
        txs, fees = parse_wise_pdf(pdf_path)
        all_txs.extend(txs)
        all_fees.extend(fees)

    if not all_txs:
        print(f"Aucune transaction exploitable dans les PDF.", file=sys.stderr)
        sys.exit(1)

    # Transactions de l'année cible
    year_txs = [t for t in all_txs if t.date.year == target_year]
    year_fees = [f for f in all_fees if f.date.year == target_year]

    if not year_txs:
        print(f"Aucune transaction pour {target_year} dans les PDF.", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Total chargé : {len(all_txs)} opérations, "
          f"{len(year_txs)} pour {target_year}")

    # --- Conversion FX (pour robustesse si devise ≠ EUR dans le futur) ---
    print(f"\n💱 Vérification des taux BCE (cache: {args.cache})...")
    fx_cache = FXCache(Path(args.cache))
    fx_log: list[dict] = []

    for tx in all_txs:
        # Le PDF fournit déjà total_eur (avec taux de change Wise).
        # On utilise FXCache uniquement si la devise n'est pas EUR.
        if tx.currency != 'EUR':
            try:
                rate, bce_date = fx_cache.get(tx.date, tx.currency)
                tx.total_eur = round(abs(tx.total_native) * rate, 4)
                if tx.type == 'sell':
                    tx.total_eur = round(tx.total_native * rate, 4)
                if tx.date.year == target_year:
                    fx_log.append({
                        'date_demandée': tx.date.isoformat(),
                        'date_BCE_utilisée': bce_date,
                        'devise': tx.currency,
                        'taux_vers_EUR': rate,
                        'même_date': 'oui' if tx.date.isoformat() == bce_date else 'non',
                        'row_id': tx.row_id,
                    })
            except Exception as e:
                print(f"  ⚠ Erreur FX {tx.date} ({tx.currency}): {e}", file=sys.stderr)
                sys.exit(2)
        else:
            if tx.date.year == target_year:
                fx_log.append({
                    'date_demandée': tx.date.isoformat(),
                    'date_BCE_utilisée': tx.date.isoformat(),
                    'devise': 'EUR',
                    'taux_vers_EUR': 1.0,
                    'même_date': 'oui',
                    'row_id': tx.row_id,
                })

    print(f"  ✓ {len(all_txs)} transactions (devise confirmée)")

    # --- Calcul PMP sur tout l'historique ---
    positions = compute_pmp_gains(all_txs)

    # Cessions de l'année cible
    gains_2074 = []
    for isin, p in positions.items():
        for g in p['realized_gains']:
            if g['date'][:4] == str(target_year):
                gains_2074.append({**g, 'isin': isin, 'name': p['name'],
                                   'country': p['country']})

    # Positions au 31/12
    last_day = date(target_year, 12, 31)
    positions_eoy = compute_pmp_gains(
        [t for t in all_txs if t.date <= last_day]
    )

    # ===================================================================
    # SORTIES CSV  →  ifu/wise/<year>/
    # ===================================================================

    def out(name: str) -> Path:
        return out_dir / f'{target_year}_{name}'

    # Journal FX
    fx_csv = out('fx_log.csv')
    with fx_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'date_demandée', 'date_BCE_utilisée', 'devise',
            'taux_vers_EUR', 'même_date', 'row_id',
        ])
        writer.writeheader()
        writer.writerows(fx_log)
    print(f"\n📊 Journal taux BCE       → {fx_csv}")

    # Transactions de l'année
    tx_csv = out('transactions.csv')
    with tx_csv.open('w', newline='', encoding='utf-8') as f:
        if year_txs:
            fields = list(asdict(year_txs[0]).keys())
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for tx in sorted(year_txs, key=lambda t: t.date):
                row = asdict(tx)
                row['date'] = tx.date.isoformat()
                writer.writerow(row)
    print(f"📊 Transactions           → {tx_csv}")

    # Dividendes (vide pour fonds capitalisants Wise)
    div_csv = out('dividendes.csv')
    with div_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'ISIN', 'Fonds', 'Montant EUR', 'Note'])
        # IE00B41N0724 et LU0852473015 sont capitalisants : pas de distributions
    print(f"📊 Dividendes             → {div_csv}  (vide — fonds capitalisants)")

    # Frais de gestion (Section III)
    fees_csv = out('fees.csv')
    with fees_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Date', 'Devise', 'Montant devise', 'Taux de change', 'Montant EUR',
            'Note fiscale',
        ])
        for fee in sorted(year_fees, key=lambda x: x.date):
            writer.writerow([
                fee.date.isoformat(), fee.currency,
                f"{fee.total_native:.2f}", f"{fee.fx_rate:.4f}",
                f"{fee.total_eur:.2f}",
                'Non déductible en PFU (art. 150-0 D CGI)',
            ])
    total_fees_eur = sum(f.total_eur for f in year_fees)
    print(f"📊 Frais de gestion       → {fees_csv}  ({total_fees_eur:.2f} EUR)")

    # Cessions formulaire 2074
    gains_csv = out('gains_2074.csv')
    with gains_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Date cession', 'ID', 'ISIN', 'Fonds', 'Pays',
            'Quantité cédée', 'Prix de cession EUR',
            'Prix de revient PMP EUR', 'PMP EUR/part',
            'Plus/moins-value EUR (PMP)', 'Montant arrondi EUR',
            'Gain FIFO Wise (informatif)',
        ])
        for g in sorted(gains_2074, key=lambda x: x['date']):
            writer.writerow([
                g['date'], g['row_id'], g['isin'], g['name'], g['country'],
                f"{g['quantity']:.6f}",
                f"{g['proceeds_eur']:.2f}",
                f"{g['cost_basis_eur']:.2f}",
                f"{g['pmp_eur']:.4f}",
                f"{g['gain_eur']:+.2f}",
                f"{round(g['gain_eur']):+d}",
                '',  # à compléter manuellement si besoin de comparer
            ])
    print(f"📊 Cessions (form. 2074)  → {gains_csv}")

    # Positions au 31/12
    summary_csv = out('summary.csv')
    with summary_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'ISIN', 'Fonds', 'Pays', 'Quantité détenue',
            'Coût total EUR (PMP)', 'PMP EUR/part',
            'Plus-values réalisées EUR', 'Formulaire',
            'Note',
        ])
        for isin, p in positions_eoy.items():
            total_realized = sum(g['gain_eur'] for g in p['realized_gains']
                                 if g['date'][:4] == str(target_year))
            pmp = (p['total_cost_eur'] / p['quantity'] if p['quantity'] > 0 else 0.0)
            note = ''
            if p['quantity'] > 1e-9:
                note = '⚠ Position ouverte — achats non listés dans les prochains PDF Wise'
            writer.writerow([
                isin, p['name'], p['country'],
                f"{p['quantity']:.6f}",
                f"{p['total_cost_eur']:.2f}",
                f"{pmp:.4f}",
                f"{total_realized:+.2f}",
                '2074',
                note,
            ])
    print(f"📊 Positions au 31/12/{target_year} → {summary_csv}")

    # ===================================================================
    # RÉCAPITULATIF CONSOLE + README.md
    # ===================================================================
    md: list[str] = []

    def h(text: str) -> None:
        print(text)
        md.append(text)

    h(f"\n# Déclaration fiscale {target_year} — Wise")
    h(f"\n> Généré le {datetime.now().strftime('%Y-%m-%d')} "
      f"· PMP calculé sur {len(all_pdfs)} PDF(s) · méthode art. 150-0 D CGI\n")

    # -- Gains 2074 --
    net_gain = sum(g['gain_eur'] for g in gains_2074)
    total_proceeds = sum(g['proceeds_eur'] for g in gains_2074)
    total_cost = sum(g['cost_basis_eur'] for g in gains_2074)

    h("## Formulaire 2074 — Valeurs mobilières (PFU 30 %)")
    h("Plus-value nette → case 3VG | Moins-value → case 3VH\n")

    if gains_2074:
        h(f"| Ventes totales EUR | Acquisitions EUR | Gain PMP EUR | Arrondi | Case |")
        h(f"|-------------------|-----------------|-------------|---------|------|")
        rounded = round(net_gain)
        box = "3VG" if rounded >= 0 else "3VH"
        h(f"| {total_proceeds:+.2f} | {total_cost:.2f} | {net_gain:+.2f} | {rounded:+d} € | {box} |")

        # Note méthode : PMP ≠ FIFO quand les achats sont à des prix différents
        h(f"\n> Gain PMP (méthode légale) : **{net_gain:+.2f} EUR** · "
          f"Comparer avec le total Section I du relevé Wise (FIFO) pour vérification.")
        h("> La méthode PMP est obligatoire pour les résidents fiscaux français "
          "(art. 150-0 D CGI). Le relevé Wise (FIFO) est fourni à titre informatif.")
    else:
        h(f"Aucune cession en {target_year} — rien à déclarer.")

    # -- Dividendes --
    h("\n## Dividendes / Distributions — formulaire 2042")
    h("Aucune distribution : IE00B41N0724 (monétaire) et LU0852473015 (capitalisant) "
      "ne versent pas de dividendes. Rien à déclarer en 2042 de ce chef.")

    # -- Frais de gestion --
    if year_fees:
        h(f"\n## Frais de gestion Wise (Section III du relevé)")
        h(f"Total {target_year} : **{total_fees_eur:.2f} EUR**\n")
        h("| Date | Montant EUR | Note |")
        h("|------|------------|------|")
        for fee in sorted(year_fees, key=lambda x: x.date):
            h(f"| {fee.date.isoformat()} | {fee.total_eur:.2f} | frais gestion mensuel |")
        h("\n> Frais de gestion de portefeuille prélevés directement sur le compte Wise. "
          "**Non déductibles sous PFU** (art. 150-0 D CGI). "
          "Sous option barème progressif, la déductibilité est à vérifier avec votre SIP.")

    # -- Positions au 31/12 --
    h(f"\n## Positions au 31/12/{target_year}\n")
    open_pos = [(isin, p) for isin, p in positions_eoy.items() if p['quantity'] > 1e-9]
    if open_pos:
        h("| ISIN | Fonds | Quantité | PMP EUR/part | Coût total EUR | Alerte |")
        h("|------|-------|---------|-------------|----------------|--------|")
        for isin, p in open_pos:
            pmp = p['total_cost_eur'] / p['quantity']
            h(f"| {isin} | {p['name']} | {p['quantity']:.6f} | {pmp:.4f} | "
              f"{p['total_cost_eur']:.2f} | "
              f"⚠ achats absents des futurs PDF |")
        h("\n> ⚠ Ces positions ouvertes n'apparaîtront PAS dans le prochain relevé fiscal Wise "
          "tant qu'elles ne seront pas cédées. Conservez les détails d'achat manuellement "
          "pour le calcul PMP de l'année suivante.")
    else:
        h(f"Toutes les positions sont fermées au 31/12/{target_year}.")

    # -- Rappels --
    h("\n## Rappels\n")
    h(f"- **Formulaire 3916** : déclarer le compte Wise chaque année "
      f"(1 500 € d'amende sinon).")
    h(f"- **Conserver les PDF Wise 10 ans** (durée de reprise fiscale).")
    h(f"- Cache des taux BCE : `{args.cache}`")
    h(f"- Les PDF Wise n'incluent pas les achats de positions non cédées (limitation Wise).")

    # -- Fichiers produits --
    h(f"\n## Fichiers produits\n")
    h(f"| Fichier | Contenu |")
    h(f"|---------|---------|")
    h(f"| `{tx_csv.name}` | Opérations de l'année |")
    h(f"| `{gains_csv.name}` | Cessions PMP — formulaire 2074 |")
    h(f"| `{div_csv.name}` | Dividendes (vide) |")
    h(f"| `{fees_csv.name}` | Frais de gestion Wise |")
    h(f"| `{summary_csv.name}` | Positions PMP au 31/12/{target_year} |")
    h(f"| `{fx_csv.name}` | Journal des taux BCE |")

    readme = out_dir / 'README.md'
    readme.write_text('\n'.join(md), encoding='utf-8')
    print(f"\n📝 Résumé                  → {readme}")


if __name__ == '__main__':
    main()
