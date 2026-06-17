"""DataUpdateCoordinator for the SAURon integration."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue, async_delete_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SauronApiClient, SauronAuthError, SauronData
from .api.exceptions import SauronNoDataError
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
            always_update=False,
        )
        self._client = client
        self._stale_threshold_h = entry.options.get(
            OPT_STALE_DATA_THRESHOLD_H, DEFAULT_STALE_DATA_THRESHOLD_H
        )

    async def _async_update_data(self) -> SauronData:
        """Fetch latest data from the SAUR API."""
        subscription_id: str = self.config_entry.data[CONF_SUBSCRIPTION_ID]
        now = datetime.now(UTC)
        # SAUR data is always J-1: query yesterday to get certified available data
        yesterday = (now.date() - timedelta(days=1))

        # Primary: latest meter index
        try:
            raw_index = await self._client.async_get_meter_last_index(subscription_id)
        except SauronAuthError as err:
            raise ConfigEntryAuthFailed from err
        except SauronNoDataError as err:
            _LOGGER.warning("Unexpected SAUR payload for %s: %s", subscription_id, err)
            raise UpdateFailed(f"SAUR payload error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"SAUR API error: {err}") from err

        data = _parse_last_index(subscription_id, raw_index, now)

        # Enrich: daily consumption — query the week containing yesterday
        daily_liters: float | None = None
        try:
            raw_weekly = await self._client.async_get_weekly(
                subscription_id, yesterday.year, yesterday.month, yesterday.day
            )
            _LOGGER.error(
                "SAURon weekly keys=%s type=%s len=%s",
                list(raw_weekly.keys()) if isinstance(raw_weekly, dict) else "NOT_DICT",
                type(raw_weekly).__name__,
                len(raw_weekly.get("consumptions", [])) if isinstance(raw_weekly, dict) else "N/A",
            )
            if isinstance(raw_weekly, dict) and raw_weekly.get("consumptions"):
                first = raw_weekly["consumptions"][0]
                _LOGGER.error("SAURon weekly first entry: %s", first)
            _LOGGER.error("SAURon weekly full: %s", str(raw_weekly)[:500])
            daily_liters = _extract_daily_liters(raw_weekly)
        except SauronAuthError:
            raise  # re-raise auth errors (will be caught by HA)
        except Exception as err:
            _LOGGER.warning("Could not fetch weekly data for %s: %s", subscription_id, err)

        # Enrich: monthly consumption
        monthly_m3: float | None = None
        try:
            raw_monthly = await self._client.async_get_monthly(
                subscription_id, now.year, now.month
            )
            monthly_m3 = _extract_period_m3(raw_monthly)
        except SauronAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Could not fetch monthly data for %s: %s", subscription_id, err)

        # Enrich: yearly consumption
        yearly_m3: float | None = None
        try:
            raw_yearly = await self._client.async_get_yearly(subscription_id, now.year)
            yearly_m3 = _extract_period_m3(raw_yearly)
        except SauronAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Could not fetch yearly data for %s: %s", subscription_id, err)

        # Enrich: weekly total — sum all Day entries from the week containing yesterday
        weekly_m3: float | None = None
        try:
            raw_weekly2 = await self._client.async_get_weekly(
                subscription_id, yesterday.year, yesterday.month, yesterday.day
            )
            weekly_m3 = _extract_week_total_m3(raw_weekly2)
        except Exception as err:
            _LOGGER.debug("Could not compute weekly total for %s: %s", subscription_id, err)

        enriched = SauronData(
            meter_info=data.meter_info,
            latest_reading=data.latest_reading,
            daily_liters=daily_liters,
            weekly_m3=weekly_m3,
            monthly_m3=monthly_m3,
            yearly_m3=yearly_m3,
        )

        # Manage stale-data Repair Issue
        reading_age_h = (
            (now.date() - enriched.latest_reading.reading_date).days * 24
            + now.hour
        )
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

        return enriched


def _parse_last_index(
    subscription_id: str, raw: dict[str, Any], fetched_at: datetime
) -> SauronData:
    """Parse GET /meter_indexes/last response.

    Real API response shape:
      { "readingDate": "2026-06-15T00:00:00", "indexValue": 1234.567 }
    """
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
      { "consumptions": [{ "startDate": "...", "value": 0.085, "rangeType": "Day" }] }

    Returns None if no Day entry found or value is negative.
    """
    consumptions = raw.get("consumptions", [])
    if not isinstance(consumptions, list):
        return None

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


def _extract_week_total_m3(raw: dict[str, Any]) -> float | None:
    """Sum all Day entries in a weekly response to get total week volume in m³."""
    consumptions = raw.get("consumptions", [])
    if not isinstance(consumptions, list):
        return None

    day_entries = [
        c for c in consumptions
        if isinstance(c, dict) and c.get("rangeType") == "Day"
    ]
    if not day_entries:
        return None

    total = sum(float(c.get("value", 0)) for c in day_entries if float(c.get("value", 0)) >= 0)
    return round(total, 3)


def _extract_period_m3(raw: dict[str, Any]) -> float | None:
    """Extract total consumption for a period (monthly or yearly response).

    The response may contain a single value or a list of sub-periods.
    We sum all non-negative values.
    """
    consumptions = raw.get("consumptions", [])
    if not isinstance(consumptions, list) or not consumptions:
        # Single-value response fallback
        value = raw.get("value") or raw.get("total") or raw.get("volume")
        if value is not None and float(value) >= 0:
            return round(float(value), 3)
        return None

    total = sum(
        float(c.get("value", 0))
        for c in consumptions
        if isinstance(c, dict) and float(c.get("value", 0)) >= 0
    )
    return round(total, 3)


def _parse_consumption(
    subscription_id: str, raw: dict[str, Any] | list[Any], fetched_at: datetime
) -> SauronData:
    """Legacy parser kept for test backward-compat. See _parse_last_index for current usage."""
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
    try:
        reading_date = date.fromisoformat(str(raw_date)[:10]) if raw_date else fetched_at.date()
    except (ValueError, TypeError):
        reading_date = fetched_at.date()

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
