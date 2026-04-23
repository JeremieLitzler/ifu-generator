import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fx_cache import FXCache


def test_fx_cache_loads_from_existing_file(tmp_path: Path) -> None:
    cache_file = tmp_path / "fx_cache.json"
    data = {"2024-01-15_CHF": {"rate": 1.05, "bce_date": "2024-01-15"}}
    cache_file.write_text(json.dumps(data))

    fx = FXCache(cache_path=cache_file)

    assert fx.cache == data


def test_fx_cache_starts_empty_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no_such_file.json"

    fx = FXCache(cache_path=missing)

    assert fx.cache == {}
