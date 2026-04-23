#!/usr/bin/env python3
"""
fx_cache.py — Cache persistant des taux de change BCE via api.frankfurter.dev.

Instancier FXCache(cache_path) pour charger/sauvegarder depuis un fichier JSON.
Ou FXCache(preloaded={...}) pour injecter un dictionnaire en mémoire (tests, etc.).
"""
import json
from datetime import date
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    import sys
    print("Manque une dépendance. Installez avec : pip install requests", file=sys.stderr)
    sys.exit(1)


def _read_json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _init_cache(cache_path: Optional[Path], preloaded: Optional[dict]) -> dict:
    if preloaded is not None:
        return dict(preloaded)
    if cache_path is not None and cache_path.exists():
        return _read_json_file(cache_path)
    return {}


class FXCache:
    """Cache persistant des taux {currency}→EUR BCE via api.frankfurter.dev."""

    API = "https://api.frankfurter.dev/v1/{date}?from={currency}&to=EUR"

    def __init__(self, cache_path: Optional[Path] = None, preloaded: Optional[dict] = None):
        self.cache_path = cache_path
        self.cache: dict = _init_cache(cache_path, preloaded)

    def _save(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.write_text(json.dumps(self.cache, indent=2, sort_keys=True))

    def _cached_entry(self, key: str) -> Optional[tuple]:
        if key not in self.cache:
            return None
        entry = self.cache[key]
        return entry['rate'], entry['bce_date']

    def _parse_payload(self, payload: dict, key: str, fallback_date: str) -> tuple:
        if 'rates' not in payload or 'EUR' not in payload['rates']:
            raise RuntimeError(f"Réponse inattendue pour {key}: {payload}")
        rate = float(payload['rates']['EUR'])
        return rate, payload.get('date', fallback_date)

    def _record_rate(self, key: str, rate: float, bce_date: str) -> None:
        self.cache[key] = {'rate': rate, 'bce_date': bce_date}
        self._save()

    def _fetch_and_store(self, d: date, currency: str, key: str) -> tuple:
        response = requests.get(self.API.format(date=d.isoformat(), currency=currency), timeout=15)
        response.raise_for_status()
        rate, bce_date = self._parse_payload(response.json(), key, d.isoformat())
        self._record_rate(key, rate, bce_date)
        return rate, bce_date

    def _get_non_eur(self, d: date, currency: str) -> tuple:
        key = f"{d.isoformat()}_{currency}"
        cached = self._cached_entry(key)
        if cached is not None:
            return cached
        return self._fetch_and_store(d, currency, key)

    def get(self, d: date, currency: str = 'CHF') -> tuple:
        """Retourne (taux→EUR, date_BCE_réelle). Retourne (1.0, date) pour EUR."""
        if currency == 'EUR':
            return 1.0, d.isoformat()
        return self._get_non_eur(d, currency)
