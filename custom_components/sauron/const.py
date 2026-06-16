"""Constants for the SAURon Home Assistant integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final[str] = "sauron"

# ── Config entry keys ─────────────────────────────────────────────────────────
CONF_LOGIN: Final[str] = "login"
CONF_PASSWORD: Final[str] = "password"
CONF_CLIENT_ID: Final[str] = "client_id"
CONF_SUBSCRIPTION_ID: Final[str] = "subscription_id"

# ── Options keys ──────────────────────────────────────────────────────────────
OPT_SCAN_INTERVAL_H: Final[str] = "scan_interval_h"
OPT_STALE_DATA_THRESHOLD_H: Final[str] = "stale_data_threshold_h"

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SCAN_INTERVAL_H: Final[int] = 4
"""Poll every 4 hours — SAUR data is updated once per day (J-1)."""

DEFAULT_STALE_DATA_THRESHOLD_H: Final[int] = 36
"""Raise a Repair Issue if the latest reading is older than 36h."""

# ── Options bounds ────────────────────────────────────────────────────────────
OPT_SCAN_INTERVAL_H_MIN: Final[int] = 1
OPT_SCAN_INTERVAL_H_MAX: Final[int] = 24
OPT_STALE_DATA_THRESHOLD_H_MIN: Final[int] = 12
OPT_STALE_DATA_THRESHOLD_H_MAX: Final[int] = 96

# ── Repair issue identifiers ─────────────────────────────────────────────────
ISSUE_STALE_DATA: Final[str] = "stale_data"
ISSUE_AUTH_FAILED: Final[str] = "auth_failed"
