"""Pytest fixtures for the SAURon test suite."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.sauron.api.models import MeterInfo, MeterReading, SauronData


@pytest.fixture
def mock_meter_info() -> MeterInfo:
    return MeterInfo(
        subscription_id="100030690002033754",
        address="1 rue de la Paix, 75001 Paris",
        meter_serial="METER123456",
        installation_date=date(2020, 1, 1),
    )


@pytest.fixture
def mock_reading(mock_meter_info: MeterInfo) -> MeterReading:
    return MeterReading(
        subscription_id=mock_meter_info.subscription_id,
        value_m3=1234.567,
        reading_date=date(2026, 6, 15),
        fetched_at=datetime(2026, 6, 16, 10, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def mock_saur_data(mock_meter_info: MeterInfo, mock_reading: MeterReading) -> SauronData:
    return SauronData(
        meter_info=mock_meter_info,
        latest_reading=mock_reading,
        daily_liters=85.3,
        weekly_m3=0.612,
        monthly_m3=2.456,
        yearly_m3=18.234,
    )


@pytest.fixture
def mock_api_client() -> AsyncMock:
    client = AsyncMock()
    client.async_authenticate = AsyncMock()
    client.async_get_latest_consumption = AsyncMock(
        return_value={
            "index": 1234.567,
            "date": "2026-06-15",
            "address": "1 rue de la Paix, 75001 Paris",
            "meterSerial": "METER123456",
        }
    )
    return client
