from pathlib import Path

import pytest

from conftest import GOLDEN_ROOT, OUTPUT_ROOT, TRANSACTIONS, FX_CACHE, YEARS, normalize


def _inputs_available() -> bool:
    return TRANSACTIONS.is_dir() and FX_CACHE.exists()


def _golden_csvs(year: int, broker: str) -> list[Path]:
    golden_dir = GOLDEN_ROOT / str(year) / broker
    if not golden_dir.is_dir():
        return []
    return sorted(f for f in golden_dir.iterdir() if f.suffix == '.csv')


def _assert_csvs_match(year: int, broker: str) -> None:
    for golden_file in _golden_csvs(year, broker):
        output_file = OUTPUT_ROOT / str(year) / broker / golden_file.name
        assert output_file.exists(), f"Missing output: {output_file.relative_to(OUTPUT_ROOT)}"
        expected = normalize(golden_file.read_text(encoding="utf-8"))
        actual = normalize(output_file.read_text(encoding="utf-8"))
        assert actual == expected, f"Content mismatch: {broker}/{year}/{golden_file.name}"


@pytest.mark.parametrize("year", YEARS)
def test_yuh_csvs_match_golden(year: int) -> None:
    if not _golden_csvs(year, "yuh"):
        pytest.skip(f"No golden yuh CSVs for {year}")
    if not _inputs_available():
        pytest.skip("transactions/ or fx_cache.json not available")
    _assert_csvs_match(year, "yuh")


@pytest.mark.parametrize("year", YEARS)
def test_wise_csvs_match_golden(year: int) -> None:
    if not _golden_csvs(year, "wise"):
        pytest.skip(f"No golden wise CSVs for {year}")
    if not _inputs_available():
        pytest.skip("transactions/ or fx_cache.json not available")
    _assert_csvs_match(year, "wise")
