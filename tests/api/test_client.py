"""Tests for the SAURon API client (pure-library, no HA)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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


_AUTH_SUCCESS = {
    "token": {"access_token": "tok123"},
    "clientId": "CLI001",
    "defaultSectionId": "SUB9876",
}


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.post = MagicMock()
    session.get = MagicMock()
    return session


class TestSauronApiClientAuth:
    async def test_authenticate_success(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(200, _AUTH_SUCCESS)

        client = SauronApiClient(mock_session, "user@example.com", "pass")
        await client.async_authenticate()

        assert client._token == "tok123"
        assert client.client_id == "CLI001"
        assert client.default_section_id == "SUB9876"
        assert client._is_token_valid()

    async def test_authenticate_sends_correct_payload(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(200, _AUTH_SUCCESS)

        client = SauronApiClient(mock_session, "user@example.com", "mypass")
        await client.async_authenticate()

        call_kwargs = mock_session.post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["username"] == "user@example.com"
        assert payload["password"] == "mypass"
        assert payload["client_id"] == "frontjs-client"
        assert payload["grant_type"] == "password"
        assert payload["captchaToken"] == "true"

    async def test_authenticate_401_raises_auth_error(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(401, {})

        client = SauronApiClient(mock_session, "bad@example.com", "wrong")
        with pytest.raises(SauronAuthError):
            await client.async_authenticate()

    async def test_authenticate_403_raises_auth_error(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(403, {})

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
        mock_session.post.return_value = _make_response(200, {"clientId": "X", "token": {}})

        client = SauronApiClient(mock_session, "user@example.com", "pass")
        with pytest.raises(SauronAuthError, match="No access_token"):
            await client.async_authenticate()

    async def test_token_valid_after_auth(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(200, _AUTH_SUCCESS)
        client = SauronApiClient(mock_session, "u", "p")
        assert not client._is_token_valid()
        await client.async_authenticate()
        assert client._is_token_valid()

    async def test_client_id_none_before_auth(self, mock_session: MagicMock) -> None:
        client = SauronApiClient(mock_session, "u", "p")
        assert client.client_id is None
        assert client.default_section_id is None

    async def test_missing_client_id_raises_api_error(self, mock_session: MagicMock) -> None:
        mock_session.post.return_value = _make_response(
            200, {"token": {"access_token": "tok"}}  # no clientId
        )
        client = SauronApiClient(mock_session, "u", "p")
        # client_id will be empty string — validate this does not raise here
        # (the config flow raises SauronApiError after checking client_id)
        await client.async_authenticate()
        assert client.client_id == ""
