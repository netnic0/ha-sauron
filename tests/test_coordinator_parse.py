"""Tests for the coordinator _parse_consumption helper (pure-library, no HA)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.sauron.coordinator import _parse_consumption
from custom_components.sauron.api.exceptions import SauronNoDataError


_NOW = datetime(2026, 6, 16, 10, 0, 0, tzinfo=UTC)
_SUB = "100030690002033754"


class TestParseConsumptionList:
    def test_single_entry_list(self) -> None:
        raw = [{"index": 1234.567, "date": "2026-06-15"}]
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.latest_reading.value_m3 == 1234.567
        assert str(data.latest_reading.reading_date) == "2026-06-15"
        assert data.daily_liters is None  # only 1 entry, no delta

    def test_two_entries_computes_daily(self) -> None:
        raw = [
            {"index": 1233.000, "date": "2026-06-14"},
            {"index": 1234.567, "date": "2026-06-15"},
        ]
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.latest_reading.value_m3 == 1234.567
        assert data.daily_liters == pytest.approx(1567.0, abs=1.0)  # 1.567 m3 * 1000

    def test_negative_delta_ignored(self) -> None:
        """A negative delta (meter reset) must not yield a negative daily consumption."""
        raw = [
            {"index": 1234.567, "date": "2026-06-14"},
            {"index": 100.000, "date": "2026-06-15"},
        ]
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.daily_liters is None

    def test_uses_last_entry_as_latest(self) -> None:
        raw = [
            {"index": 100.0, "date": "2026-06-13"},
            {"index": 101.0, "date": "2026-06-14"},
            {"index": 102.5, "date": "2026-06-15"},
        ]
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.latest_reading.value_m3 == 102.5
        assert data.daily_liters == pytest.approx(1500.0, abs=1.0)  # 1.5 m3


class TestParseConsumptionDict:
    def test_dict_with_pre_computed_daily(self) -> None:
        raw = {"index": 1234.567, "date": "2026-06-15", "dailyConsumption": 0.085}
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.daily_liters == pytest.approx(85.0, abs=0.5)

    def test_dict_without_daily(self) -> None:
        raw = {"index": 1234.567, "date": "2026-06-15"}
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.daily_liters is None

    def test_dict_fallback_date_from_fetched_at(self) -> None:
        raw = {"value": 500.0}  # no date field
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.latest_reading.reading_date == _NOW.date()

    def test_dict_alternative_field_names(self) -> None:
        raw = {"volume": 999.9, "dateRelevee": "2026-06-10"}
        data = _parse_consumption(_SUB, raw, _NOW)
        assert data.latest_reading.value_m3 == 999.9
        assert str(data.latest_reading.reading_date) == "2026-06-10"


class TestParseConsumptionErrors:
    def test_empty_list_raises(self) -> None:
        with pytest.raises(SauronNoDataError):
            _parse_consumption(_SUB, [], _NOW)

    def test_non_list_non_dict_raises(self) -> None:
        with pytest.raises(SauronNoDataError):
            _parse_consumption(_SUB, None, _NOW)  # type: ignore[arg-type]
