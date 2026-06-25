"""Async HTTP client for the SAUR API (apib2c.azure.saurclient.fr).

Authentication flow:
  POST /admin/v2/auth  →  { token: { access_token }, clientId, defaultSectionId }

The reCAPTCHA v3 field accepted by the API is a literal string "true",
not a real token — the server-side check is not enforced for non-browser
clients. We replicate the same payload as the official web app.

Token lifecycle:
  - Stored in memory only (never persisted to config entry)
  - Re-authenticated on 401/403 (one retry then raises SauronAuthError)
  - On SauronAuthError, the coordinator raises ConfigEntryAuthFailed
    which triggers HA's native re-authentication flow

Field names are sourced from reverse-engineering the eyeonsaur-ha integration
and the Saur_fr_client library (https://github.com/cekage/Saur_fr_client).
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .exceptions import SauronApiError, SauronAuthError, SauronNoDataError

_LOGGER = logging.getLogger(__name__)

_BASE_URL = "https://apib2c.azure.saurclient.fr"
_AUTH_ENDPOINT = "/admin/v2/auth"
_WEBSITE_AREAS_ENDPOINT = "/admin/users/v2/website_areas/{client_id}"
_DELIVERY_POINTS_ENDPOINT = "/deli/section_subscriptions/{section_id}/supply_areas/delivery_points"
_METER_INDEXES_ENDPOINT = "/deli/section_subscriptions/{section_id}/meter_indexes/last"
_CONSUMPTIONS_ENDPOINT = "/deli/section_subscription/{section_id}/consumptions"
_CONSUMPTIONS_WEEKLY_ENDPOINT = "/deli/section_subscription/{section_id}/consumptions/weekly"
_CONSUMPTIONS_MONTHLY_ENDPOINT = "/deli/section_subscription/{section_id}/consumptions/monthly"
_CONSUMPTIONS_YEARLY_ENDPOINT = "/deli/section_subscription/{section_id}/consumptions/yearly"


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
        self._client_id: str | None = None
        self._default_section_id: str | None = None

    # ── Authentication ────────────────────────────────────────────────────────

    async def async_authenticate(self) -> None:
        """Obtain a fresh Bearer token and discover client_id.

        Raises SauronAuthError on invalid credentials.
        Raises SauronApiError on unexpected HTTP errors.

        Response structure:
          { "token": { "access_token": "..." }, "clientId": "...", "defaultSectionId": "..." }
        """
        payload = {
            "username": self._login,
            "password": self._password,
            "client_id": "frontjs-client",
            "grant_type": "password",
            "scope": "api-scope",
            "isRecaptchaV3": True,
            "captchaToken": "true",
        }
        async with self._session.post(
            f"{_BASE_URL}{_AUTH_ENDPOINT}", json=payload
        ) as resp:
            if resp.status in (401, 403):
                raise SauronAuthError("Invalid SAUR credentials")
            if resp.status != 200:
                raise SauronApiError(resp.status, await resp.text())
            data: dict[str, Any] = await resp.json()

        # Extract token from nested {"token": {"access_token": "..."}}
        token_obj = data.get("token") or {}
        token = token_obj.get("access_token") if isinstance(token_obj, dict) else None
        if not token:
            raise SauronAuthError("No access_token in auth response")

        self._token = token
        self._client_id = str(data.get("clientId", ""))
        self._default_section_id = str(data.get("defaultSectionId", ""))
        # Probe response shape — Plan A §0: confirm whether SAUR emits expires_in.
        # Drives the choice between a real TTL and the DEFAULT_TOKEN_TTL_S fallback.
        _LOGGER.debug(
            "SAUR auth response keys=%s expires_in=%s",
            list(data.keys()),
            data.get("expires_in"),
        )
        _LOGGER.debug(
            "SAUR authenticated: client_id=%s, default_section_id=%s",
            self._client_id,
            self._default_section_id,
        )

    @property
    def client_id(self) -> str | None:
        return self._client_id

    @property
    def default_section_id(self) -> str | None:
        return self._default_section_id

    def _is_token_valid(self) -> bool:
        return bool(self._token)

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
            if resp.status not in (401, 403):
                if resp.status != 200:
                    raise SauronApiError(resp.status, await resp.text())
                return await resp.json()

        # Token rejected — retry once after re-auth
        _LOGGER.debug("Token rejected (%d), re-authenticating", resp.status)
        self._token = None
        await self.async_authenticate()
        headers = {"Authorization": f"Bearer {self._token}"}

        async with self._session.get(
            f"{_BASE_URL}{path}", headers=headers, params=params
        ) as resp2:
            if resp2.status in (401, 403):
                raise SauronAuthError("Re-authentication failed")
            if resp2.status != 200:
                raise SauronApiError(resp2.status, await resp2.text())
            return await resp2.json()

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def async_get_website_areas(self, client_id: str) -> dict[str, Any]:
        """GET /admin/users/v2/website_areas/{client_id} — account contracts."""
        path = _WEBSITE_AREAS_ENDPOINT.format(client_id=client_id)
        return await self._get(path)

    async def async_get_delivery_points(self, section_id: str) -> dict[str, Any]:
        """GET delivery points for a section subscription.

        Response: dict with keys:
          meter, geographicAddress, sectionSubscriptionId, ...
        """
        path = _DELIVERY_POINTS_ENDPOINT.format(section_id=section_id)
        data = await self._get(path)
        if not isinstance(data, dict):
            raise SauronNoDataError(f"Expected dict from delivery_points, got {type(data)}")
        return data

    async def async_get_meter_last_index(self, section_id: str) -> dict[str, Any]:
        """GET the latest meter index reading.

        Response: { "readingDate": "ISO datetime", "indexValue": float }
        """
        path = _METER_INDEXES_ENDPOINT.format(section_id=section_id)
        return await self._get(path)

    # ── Consumption endpoints ─────────────────────────────────────────────────

    async def async_get_consumptions(self, section_id: str) -> dict[str, Any]:
        """GET the latest consumption snapshot."""
        path = _CONSUMPTIONS_ENDPOINT.format(section_id=section_id)
        return await self._get(path)

    async def async_get_weekly(
        self, section_id: str, year: int, month: int, day: int
    ) -> dict[str, Any]:
        path = _CONSUMPTIONS_WEEKLY_ENDPOINT.format(section_id=section_id)
        return await self._get(path, params={"year": year, "month": month, "day": day})

    async def async_get_monthly(
        self, section_id: str, year: int, month: int
    ) -> dict[str, Any]:
        path = _CONSUMPTIONS_MONTHLY_ENDPOINT.format(section_id=section_id)
        return await self._get(path, params={"year": year, "month": month})

    async def async_get_yearly(self, section_id: str, year: int) -> dict[str, Any]:
        path = _CONSUMPTIONS_YEARLY_ENDPOINT.format(section_id=section_id)
        return await self._get(path, params={"year": year})
