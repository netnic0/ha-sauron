"""DataUpdateCoordinator for the SAURon integration."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue, async_delete_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SauronApiClient, SauronAuthError, SauronData
from .api.models import MeterInfo, MeterReading
from .const import (
    CONF_SUBSCRIPTION_ID,
    DEFAULT_SCAN_INTERVAL_H,
    DEFAULT_STALE_DATA_THRESHOLD_H,
    DOMAIN,
    ISSUE_STALE_DATA,
    OPT_SCAN_INTERVAL_H,
    OPT_STALE_DATA_THRESHOLD_H,
)

_LOGGER = logging.getLogger(__name__)


class SauronCoordinator(DataUpdateCoordinator[SauronData]):
    """Fetch SAUR water consumption data on a configurable schedule."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: SauronApiClient,
        entry: ConfigEntry,
    ) -> None:
        scan_interval_h = entry.options.get(OPT_SCAN_INTERVAL_H, DEFAULT_SCAN_INTERVAL_H)
        super().__init__(
            hass,
            _LOGGER,
            name=f"SAURon ({entry.data[CONF_SUBSCRIPTION_ID]})",
            update_interval=timedelta(hours=scan_interval_h),
            config_entry=entry,
        )
        self._client = client
        self._stale_threshold_h = entry.options.get(
            OPT_STALE_DATA_THRESHOLD_H, DEFAULT_STALE_DATA_THRESHOLD_H
        )

    async def _async_update_data(self) -> SauronData:
        """Fetch latest data from the SAUR API."""
        subscription_id: str = self.config_entry.data[CONF_SUBSCRIPTION_ID]
        now = datetime.now(UTC)

        try:
            raw_index = await self._client.async_get_meter_last_index(subscription_id)
        except SauronAuthError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"SAUR API error: {err}") from err

        data = _parse_last_index(subscription_id, raw_index, now)

        # Try to enrich with daily consumption from weekly endpoint
        try:
            today = now.date()
            raw_weekly = await self._client.async_get_weekly(
                subscription_id, today.year, today.month, today.day
            )
            daily_liters = _extract_daily_liters(raw_weekly)
        except Exception:
            daily_liters = None

        data = SauronData(
            meter_info=data.meter_info,
            latest_reading=data.latest_reading,
            daily_liters=daily_liters,
        )

        # Manage stale-data Repair Issue
        reading_age_h = (
            now
            - datetime.combine(data.latest_reading.reading_date, datetime.min.time(), tzinfo=UTC)
        ).total_seconds() / 3600
        issue_id = f"{ISSUE_STALE_DATA}_{self.config_entry.entry_id}"

        if reading_age_h > self._stale_threshold_h:
            async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key=ISSUE_STALE_DATA,
                translation_placeholders={
                    "subscription_id": subscription_id,
                    "age_h": f"{reading_age_h:.0f}",
                },
            )
        else:
            async_delete_issue(self.hass, DOMAIN, issue_id)

        return data


def _parse_last_index(
    subscription_id: str, raw: dict[str, Any], fetched_at: datetime
) -> SauronData:
    """Parse GET /meter_indexes/last response.

    Real API response shape:
      { "readingDate": "2026-06-15T00:00:00", "indexValue": 1234.567 }
    """
    from .api.exceptions import SauronNoDataError

    if not isinstance(raw, dict):
        raise SauronNoDataError(f"Expected dict from meter_indexes/last, got {type(raw)}")

    index_value = raw.get("indexValue")
    if index_value is None:
        raise SauronNoDataError("indexValue missing from meter_indexes/last response")

    raw_date = raw.get("readingDate", "")
    try:
        reading_date = date.fromisoformat(str(raw_date)[:10])
    except (ValueError, TypeError):
        reading_date = fetched_at.date()

    meter_info = MeterInfo(
        subscription_id=subscription_id,
        address="",
        meter_serial="",
        installation_date=None,
    )
    reading = MeterReading(
        subscription_id=subscription_id,
        value_m3=float(index_value),
        reading_date=reading_date,
        fetched_at=fetched_at,
    )
    return SauronData(meter_info=meter_info, latest_reading=reading)


def _extract_daily_liters(raw: dict[str, Any]) -> float | None:
    """Extract yesterday's consumption in litres from a weekly response.

    Real API response shape:
      { "consumptions": [{ "startDate": "2026-06-15 00:00:00", "value": 0.085, "rangeType": "Day" }] }

    The most recent Day entry is used. Value is in m³ → convert to litres.
    Returns None if no Day entry is found or value is negative.
    """
    consumptions = raw.get("consumptions", [])
    if not isinstance(consumptions, list):
        return None

    # Filter to Day-range entries and take the last one (most recent)
    day_entries = [
        c for c in consumptions
        if isinstance(c, dict) and c.get("rangeType") == "Day"
    ]
    if not day_entries:
        return None

    last = day_entries[-1]
    value_m3 = last.get("value")
    if value_m3 is None or float(value_m3) < 0:
        return None

    return round(float(value_m3) * 1000, 1)


def _parse_consumption(
    subscription_id: str, raw: dict[str, Any] | list[Any], fetched_at: datetime
) -> SauronData:
    """Legacy parser kept for test compatibility.

    Handles both the old /consumptions endpoint (dict or list) and the new
    /meter_indexes/last shape. PR #2 will consolidate to _parse_last_index.
    """
    from datetime import date as date_type

    from .api.exceptions import SauronNoDataError

    daily_liters: float | None = None

    if isinstance(raw, list) and raw:
        latest = raw[-1]
        if len(raw) >= 2:
            prev = raw[-2]
            prev_val = float(
                prev.get("index") or prev.get("value") or prev.get("volume") or 0.0
            )
            curr_val = float(
                latest.get("index") or latest.get("value") or latest.get("volume") or 0.0
            )
            delta_m3 = curr_val - prev_val
            if delta_m3 >= 0:
                daily_liters = round(delta_m3 * 1000, 1)
    elif isinstance(raw, dict):
        latest = raw
        daily_raw = (
            raw.get("dailyConsumption")
            or raw.get("daily_volume")
            or raw.get("volumeJour")
        )
        if daily_raw is not None:
            daily_liters = round(float(daily_raw) * 1000, 1)
    else:
        raise SauronNoDataError("Empty consumption payload")

    value_m3 = float(
        latest.get("index") or latest.get("value") or latest.get("volume") or 0.0
    )
    raw_date = latest.get("date") or latest.get("readingDate") or latest.get("dateRelevee")
    reading_date = (
        date_type.fromisoformat(str(raw_date)[:10]) if raw_date else fetched_at.date()
    )

    meter_info = MeterInfo(
        subscription_id=subscription_id,
        address=str(latest.get("address") or latest.get("adresse") or ""),
        meter_serial=str(latest.get("meterSerial") or latest.get("serialNumber") or ""),
        installation_date=None,
    )
    reading = MeterReading(
        subscription_id=subscription_id,
        value_m3=value_m3,
        reading_date=reading_date,
        fetched_at=fetched_at,
    )
    return SauronData(
        meter_info=meter_info,
        latest_reading=reading,
        daily_liters=daily_liters,
    )
