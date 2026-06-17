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
    client.async_get_meter_last_index = AsyncMock(
        return_value={
            "indexValue": 1234.567,
            "readingDate": "2026-06-15T00:00:00",
        }
    )
    client.async_get_weekly = AsyncMock(
        return_value={
            "consumptions": [
                {"startDate": "2026-06-09T00:00:00", "endDate": "2026-06-10T00:00:00", "value": 0.085, "rangeType": "Day"},
                {"startDate": "2026-06-10T00:00:00", "endDate": "2026-06-11T00:00:00", "value": 0.092, "rangeType": "Day"},
            ],
            "isRemoteReading": True,
        }
    )
    client.async_get_monthly = AsyncMock(return_value={"consumptions": []})
    client.async_get_yearly = AsyncMock(return_value={"consumptions": []})
    return client
