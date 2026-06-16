"""Async HTTP client for the SAUR API (apib2c.azure.saurclient.fr).

Authentication flow:
  POST /admin/v2/auth  →  access_token (Bearer)

The reCAPTCHA v3 field accepted by the API is a literal string "true",
not a real token — the server-side check is not enforced for non-browser
clients. We replicate the same payload as the official web app.

Token lifecycle:
  - Stored in memory only (never persisted to config entry)
  - Re-authenticated on 401/403 (one retry then raises SauronAuthError)
  - On SauronAuthError, the coordinator raises ConfigEntryAuthFailed
    which triggers HA's native re-authentication flow
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .exceptions import SauronApiError, SauronAuthError, SauronNoDataError

_LOGGER = logging.getLogger(__name__)

_BASE_URL = "https://apib2c.azure.saurclient.fr"
_AUTH_ENDPOINT = "/admin/v2/auth"
_BRAND_ENDPOINT = "/admin/v2/brandparameter"
_SUBSCRIPTIONS_ENDPOINT = "/deli/section_subscriptions/{id}/supply_areas/delivery_points"
_CONSUMPTIONS_ENDPOINT = "/deli/section_subscription/{id}/consumptions"
_CONSUMPTIONS_DAILY_ENDPOINT = "/deli/section_subscription/{id}/consumptions/daily"
_CONSUMPTIONS_WEEKLY_ENDPOINT = "/deli/section_subscription/{id}/consumptions/weekly"
_CONSUMPTIONS_MONTHLY_ENDPOINT = "/deli/section_subscription/{id}/consumptions/monthly"
_CONSUMPTIONS_YEARLY_ENDPOINT = "/deli/section_subscription/{id}/consumptions/yearly"

_TOKEN_MARGIN = timedelta(minutes=5)
"""Refresh token this many minutes before it expires."""


class SauronApiClient:
    """Async SAUR API client — one instance per config entry."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        login: str,
        password: str,
    ) -> None:
        self._session = session
        self._login = login
        self._password = password
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    # ── Authentication ────────────────────────────────────────────────────────

    async def async_authenticate(self) -> None:
        """Obtain a fresh Bearer token. Raises SauronAuthError on failure."""
        payload = {
            "login": self._login,
            "password": self._password,
            "isRecaptchaV3": True,
            "captchaToken": "true",
        }
        async with self._session.post(
            f"{_BASE_URL}{_AUTH_ENDPOINT}", json=payload
        ) as resp:
            if resp.status == 401 or resp.status == 403:
                raise SauronAuthError("Invalid SAUR credentials")
            if resp.status != 200:
                raise SauronApiError(resp.status, await resp.text())
            data: dict[str, Any] = await resp.json()

        token = data.get("access_token") or data.get("accessToken")
        if not token:
            raise SauronAuthError("No access_token in auth response")

        self._token = token
        # SAUR tokens typically expire in 3600s; fall back to 50 minutes if absent
        expires_in = int(data.get("expires_in", 3000))
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        _LOGGER.debug("SAUR token refreshed, expires in %ds", expires_in)

    def _is_token_valid(self) -> bool:
        if not self._token or not self._token_expires_at:
            return False
        return datetime.now(UTC) < (self._token_expires_at - _TOKEN_MARGIN)

    async def _ensure_token(self) -> str:
        if not self._is_token_valid():
            await self.async_authenticate()
        assert self._token is not None  # noqa: S101
        return self._token

    # ── Generic request helper ────────────────────────────────────────────────

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET with automatic token refresh on 401."""
        token = await self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with self._session.get(
            f"{_BASE_URL}{path}", headers=headers, params=params
        ) as resp:
            if resp.status in (401, 403):
                # Token may have been revoked server-side — retry once
                _LOGGER.debug("Token rejected (%d), re-authenticating", resp.status)
                await self.async_authenticate()
                token = self._token
                headers = {"Authorization": f"Bearer {token}"}
            else:
                if resp.status != 200:
                    raise SauronApiError(resp.status, await resp.text())
                return await resp.json()

        # Second attempt after re-auth
        async with self._session.get(
            f"{_BASE_URL}{path}", headers=headers, params=params
        ) as resp:
            if resp.status in (401, 403):
                raise SauronAuthError("Re-authentication failed")
            if resp.status != 200:
                raise SauronApiError(resp.status, await resp.text())
            return await resp.json()

    # ── Business endpoints ────────────────────────────────────────────────────

    async def async_get_subscriptions(self, client_id: str) -> list[dict[str, Any]]:
        """Return the list of delivery points / meters for a client account."""
        path = _SUBSCRIPTIONS_ENDPOINT.format(id=client_id)
        data = await self._get(path)
        if not isinstance(data, list):
            raise SauronNoDataError(f"Unexpected subscriptions payload: {type(data)}")
        return data

    async def async_get_latest_consumption(self, subscription_id: str) -> dict[str, Any]:
        """Return the latest consumption record for a subscription."""
        path = _CONSUMPTIONS_ENDPOINT.format(id=subscription_id)
        data = await self._get(path)
        if not isinstance(data, (dict, list)):
            raise SauronNoDataError("Empty consumption payload")
        return data  # type: ignore[return-value]

    async def async_get_weekly(
        self, subscription_id: str, year: int, month: int, day: int
    ) -> dict[str, Any]:
        path = _CONSUMPTIONS_WEEKLY_ENDPOINT.format(id=subscription_id)
        return await self._get(path, params={"year": year, "month": month, "day": day})

    async def async_get_monthly(
        self, subscription_id: str, year: int, month: int
    ) -> dict[str, Any]:
        path = _CONSUMPTIONS_MONTHLY_ENDPOINT.format(id=subscription_id)
        return await self._get(path, params={"year": year, "month": month})

    async def async_get_yearly(self, subscription_id: str, year: int) -> dict[str, Any]:
        path = _CONSUMPTIONS_YEARLY_ENDPOINT.format(id=subscription_id)
        return await self._get(path, params={"year": year})
