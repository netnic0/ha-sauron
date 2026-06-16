"""Tests for the SAURon API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sauron.api.client import SauronApiClient
from custom_components.sauron.api.exceptions import SauronApiError, SauronAuthError


def _make_response(status: int, json_data: object) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    resp.text = AsyncMock(return_value=str(json_data))
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.post = MagicMock()
    session.get = MagicMock()
    return session


class TestSauronApiClientAuth:
    async def test_authenticate_success(self, mock_session: MagicMock) -> None:
        auth_response = _make_response(
            200, {"access_token": "tok123", "expires_in": 3600}
        )
        mock_session.post.return_value = auth_response

        client = SauronApiClient(mock_session, "user@example.com", "pass")
        await client.async_authenticate()

        assert client._token == "tok123"
        assert client._is_token_valid()

    async def test_authenticate_401_raises_auth_error(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(401, {})

        client = SauronApiClient(mock_session, "bad@example.com", "wrong")
        with pytest.raises(SauronAuthError):
            await client.async_authenticate()

    async def test_authenticate_500_raises_api_error(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(500, "Internal Server Error")

        client = SauronApiClient(mock_session, "user@example.com", "pass")
        with pytest.raises(SauronApiError) as exc_info:
            await client.async_authenticate()
        assert exc_info.value.status == 500

    async def test_authenticate_missing_token_raises_auth_error(
        self, mock_session: MagicMock
    ) -> None:
        mock_session.post.return_value = _make_response(200, {"no_token": True})

        client = SauronApiClient(mock_session, "user@example.com", "pass")
        with pytest.raises(SauronAuthError, match="No access_token"):
            await client.async_authenticate()

    async def test_token_valid_after_auth(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(
            200, {"access_token": "tok", "expires_in": 3600}
        )
        client = SauronApiClient(mock_session, "u", "p")
        assert not client._is_token_valid()
        await client.async_authenticate()
        assert client._is_token_valid()
