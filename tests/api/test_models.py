"""Tests for SAURon data models."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from custom_components.sauron.api.models import MeterInfo, MeterReading, SauronData


def test_meter_info_frozen() -> None:
    info = MeterInfo(
        subscription_id="123",
        address="Test",
        meter_serial="SN001",
        installation_date=None,
    )
    with pytest.raises(AttributeError):
        info.subscription_id = "456"  # type: ignore[misc]


def test_saur_data_defaults() -> None:
    info = MeterInfo(subscription_id="123", address="", meter_serial="", installation_date=None)
    reading = MeterReading(
        subscription_id="123",
        value_m3=100.0,
        reading_date=date(2026, 6, 15),
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
    )
    data = SauronData(meter_info=info, latest_reading=reading)
    assert data.daily_liters is None
    assert data.weekly_m3 is None
    assert data.monthly_m3 is None
    assert data.yearly_m3 is None
    assert data.consumptions == ()


def test_meter_reading_value(mock_reading: MeterReading) -> None:
    assert mock_reading.value_m3 == 1234.567
    assert mock_reading.reading_date == date(2026, 6, 15)
