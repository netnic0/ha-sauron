"""Coordinator exception-mapping tests (Plan A v2 §4.3 — RC-4).

Verifies that SauronAuthError → ConfigEntryAuthFailed and
SauronTransientError → UpdateFailed at the coordinator layer, across
all three endpoint try/except blocks (primary, monthly, yearly).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.sauron.api.exceptions import (
    SauronAuthError,
    SauronTransientError,
)
from custom_components.sauron.coordinator import SauronCoordinator


def _make_coordinator(client: Any) -> SauronCoordinator:
    """Build a SauronCoordinator wired to a fake client and a stub entry."""
    entry = MagicMock()
    entry.entry_id = "entry_1"
    entry.data = {"subscription_id": "SUB001"}
    entry.options = {}
    hass = MagicMock()
    coordinator = SauronCoordinator(hass, client, entry)
    # The real DataUpdateCoordinator sets self.config_entry and self.hass
    # from kwargs; our stub doesn't, so wire them explicitly for tests.
    coordinator.config_entry = entry
    coordinator.hass = hass
    return coordinator


def _ok_index_payload() -> dict[str, Any]:
    return {"indexValue": 100.0, "readingDate": "2026-06-15T00:00:00"}


class TestExceptionMappingPrimary:
    """Block 1 — last meter index (the mandatory data path)."""

    async def test_auth_error_raises_config_entry_auth_failed(self) -> None:
        client = AsyncMock()
        client.async_get_meter_last_index = AsyncMock(
            side_effect=SauronAuthError("bad creds")
        )

        coordinator = _make_coordinator(client)
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    async def test_transient_error_raises_update_failed_not_auth(self) -> None:
        client = AsyncMock()
        client.async_get_meter_last_index = AsyncMock(
            side_effect=SauronTransientError("/auth flaky")
        )

        coordinator = _make_coordinator(client)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


class TestExceptionMappingMonthlyEnrichment:
    """Block 2 — monthly endpoint (enrichment, non-fatal except for auth)."""

    async def test_auth_error_on_monthly_raises_config_entry_auth_failed(self) -> None:
        client = AsyncMock()
        client.async_get_meter_last_index = AsyncMock(return_value=_ok_index_payload())
        client.async_get_monthly = AsyncMock(side_effect=SauronAuthError("bad creds"))
        client.async_get_yearly = AsyncMock(return_value={"consumptions": []})

        coordinator = _make_coordinator(client)
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    async def test_transient_error_on_monthly_keeps_primary_data(self) -> None:
        client = AsyncMock()
        client.async_get_meter_last_index = AsyncMock(return_value=_ok_index_payload())
        client.async_get_monthly = AsyncMock(
            side_effect=SauronTransientError("SAUR backend hiccup")
        )
        client.async_get_yearly = AsyncMock(return_value={"consumptions": []})

        coordinator = _make_coordinator(client)
        data = await coordinator._async_update_data()

        # Primary data is preserved; enrichment fields stay None.
        assert data.latest_reading.value_m3 == 100.0
        assert data.daily_liters is None
        assert data.weekly_m3 is None
        assert data.monthly_m3 is None


class TestExceptionMappingYearlyEnrichment:
    """Block 3 — yearly endpoint (enrichment, non-fatal except for auth)."""

    async def test_transient_error_on_yearly_keeps_primary_data(self) -> None:
        client = AsyncMock()
        client.async_get_meter_last_index = AsyncMock(return_value=_ok_index_payload())
        client.async_get_monthly = AsyncMock(return_value={"consumptions": []})
        client.async_get_yearly = AsyncMock(
            side_effect=SauronTransientError("transient yearly")
        )

        coordinator = _make_coordinator(client)
        data = await coordinator._async_update_data()

        assert data.latest_reading.value_m3 == 100.0
        assert data.yearly_m3 is None
