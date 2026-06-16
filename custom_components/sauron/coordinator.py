"""DataUpdateCoordinator for the SAURon integration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue, async_delete_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SauronApiClient, SauronAuthError, SauronData
from .api.models import MeterInfo, MeterReading, SauronData
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
            raw = await self._client.async_get_latest_consumption(subscription_id)
        except SauronAuthError as err:
            # Trigger HA's native re-authentication flow
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"SAUR API error: {err}") from err

        data = _parse_consumption(subscription_id, raw, now)

        # Manage stale-data Repair Issue
        reading_age_h = (now - datetime.combine(
            data.latest_reading.reading_date, datetime.min.time(), tzinfo=UTC
        )).total_seconds() / 3600
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


def _parse_consumption(
    subscription_id: str, raw: dict | list, fetched_at: datetime
) -> SauronData:
    """Parse the SAUR /consumptions API response into a SauronData snapshot.

    The SAUR API can return either a dict or a list depending on the endpoint.
    This function normalises the response into our frozen dataclasses.
    """
    from datetime import date

    # Normalise: the endpoint may return a list of readings or a single dict
    if isinstance(raw, list) and raw:
        latest = raw[-1]
    elif isinstance(raw, dict):
        latest = raw
    else:
        from .api.exceptions import SauronNoDataError
        raise SauronNoDataError("Empty consumption payload")

    # Extract index value and date — field names vary by firmware/API version
    value_m3 = float(
        latest.get("index")
        or latest.get("value")
        or latest.get("volume")
        or 0.0
    )
    raw_date = latest.get("date") or latest.get("readingDate") or latest.get("dateRelevee")
    reading_date = (
        date.fromisoformat(str(raw_date)[:10]) if raw_date else fetched_at.date()
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

    return SauronData(meter_info=meter_info, latest_reading=reading)
