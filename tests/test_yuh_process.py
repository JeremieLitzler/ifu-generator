import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fx_cache import FXCache
from yuh_csv_ifu import process

REPO_ROOT = Path(__file__).parent.parent
TRANSACTIONS = REPO_ROOT / "transactions"
GOLDEN_ROOT = REPO_ROOT / "ifu"
FX_CACHE_PATH = REPO_ROOT / "fx_cache.json"
YEARS = [2023, 2024, 2025]

_DATE_PATTERN = re.compile(r'Généré le \d{4}-\d{2}-\d{2}')


def _inputs_available() -> bool:
    return TRANSACTIONS.is_dir() and FX_CACHE_PATH.exists()


def _all_yuh_csvs() -> list[Path]:
    upper = sorted(TRANSACTIONS.glob("yuh_ACTIVITIES_REPORT-*.CSV"))
    lower = sorted(TRANSACTIONS.glob("yuh_ACTIVITIES_REPORT-*.csv"))
    return sorted(set(upper + lower))


def _has_yuh_csv(year: int) -> bool:
    return bool(
        list(TRANSACTIONS.glob(f"yuh_ACTIVITIES_REPORT-{year}.CSV"))
        + list(TRANSACTIONS.glob(f"yuh_ACTIVITIES_REPORT-{year}.csv"))
    )


def _golden_csvs(year: int) -> list[Path]:
    golden_dir = GOLDEN_ROOT / str(year) / "yuh"
    if not golden_dir.is_dir():
        return []
    return sorted(f for f in golden_dir.iterdir() if f.suffix == '.csv')


def _normalize(content: str) -> str:
    lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    stripped = [_DATE_PATTERN.sub('Généré le DATE', line.rstrip()) for line in lines]
    return '\n'.join(stripped).strip()


def _build_fx() -> FXCache:
    return FXCache(cache_path=FX_CACHE_PATH)


def _read_all_csvs() -> list[bytes]:
    return [p.read_bytes() for p in _all_yuh_csvs()]


@pytest.mark.parametrize("year", YEARS)
def test_process_returns_expected_keys(year: int) -> None:
    if not _inputs_available():
        pytest.skip("transactions/ or fx_cache.json not available")
    if not _has_yuh_csv(year):
        pytest.skip(f"No Yuh CSV for {year}")

    outputs = process(_read_all_csvs(), year, _build_fx())

    expected_keys = {
        f'{year}_fx_log.csv',
        f'{year}_transactions.csv',
        f'{year}_dividendes.csv',
        f'{year}_gains_2074.csv',
        f'{year}_gains_2086.csv',
        f'{year}_summary.csv',
        'README.md',
    }
    assert set(outputs.keys()) == expected_keys


@pytest.mark.parametrize("year", YEARS)
def test_process_csv_content_matches_golden(year: int) -> None:
    if not _inputs_available():
        pytest.skip("transactions/ or fx_cache.json not available")
    golden_files = _golden_csvs(year)
    if not golden_files:
        pytest.skip(f"No golden Yuh CSVs for {year}")

    outputs = process(_read_all_csvs(), year, _build_fx())

    for golden_file in golden_files:
        assert golden_file.name in outputs, f"Missing key in outputs: {golden_file.name}"
        expected = _normalize(golden_file.read_text(encoding="utf-8"))
        actual = _normalize(outputs[golden_file.name])
        assert actual == expected, f"Content mismatch: yuh/{year}/{golden_file.name}"
