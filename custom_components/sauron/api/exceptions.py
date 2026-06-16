"""Typed exception hierarchy for the SAURon API client."""

from __future__ import annotations


class SauronError(Exception):
    """Base class for all SAURon errors."""


class SauronAuthError(SauronError):
    """Authentication failed (bad credentials or expired token)."""


class SauronApiError(SauronError):
    """Unexpected HTTP error from the SAUR API."""

    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class SauronNoDataError(SauronError):
    """The API returned an empty or unexpected payload."""
