# SAURon — Home Assistant integration for SAUR water consumption

[![HACS](https://img.shields.io/badge/HACS-Integration-blue.svg)](https://hacs.xyz)
[![GitHub release](https://img.shields.io/github/v/release/netnic0/ha-sauron)](https://github.com/netnic0/ha-sauron/releases)

A modern, typed, Silver-quality HACS integration for monitoring your [SAUR](https://www.saur.fr) water consumption directly in Home Assistant.

## Features

- **7 sensor entities** per meter: absolute index, last reading date, daily/weekly/monthly/yearly consumption, data age
- **Energy Dashboard** compatible: the `last_index` sensor feeds natively into HA's Water panel
- **Multi-account** ready: add multiple config entries for multiple SAUR subscriptions
- **Repair Issues**: HA alerts when data becomes stale (configurable threshold)
- **Re-authentication flow**: seamless credential update without removing the integration
- **Options flow**: configure polling interval and stale-data threshold at runtime
- **i18n**: English and French (DE/ES planned)
- **Silver quality tier**: typed, tested, no external library dependencies

## Installation

### HACS (recommended)

1. In HACS, click **+ Explore & Download Repositories**
2. Search for **SAURon**
3. Download and restart Home Assistant

### Manual

Copy `custom_components/sauron/` to your `config/custom_components/` folder and restart.

## Configuration

1. Go to **Settings → Integrations → Add Integration**
2. Search for **SAURon**
3. Enter your SAUR customer portal credentials (same as [mon-espace.saurclient.fr](https://mon-espace.saurclient.fr))

## Sensors

| Entity | Unit | Description |
|---|---|---|
| Water index | m³ | Absolute meter index (feeds Energy Dashboard Water) |
| Last reading date | — | Date of the latest DTU-transmitted reading |
| Daily consumption | L | Yesterday's consumption |
| Weekly consumption | m³ | Current week |
| Monthly consumption | m³ | Current month |
| Yearly consumption | m³ | Current year |
| Data age | h | Hours since the last reading (diagnostic) |

## Energy Dashboard

Add `sensor.sauron_*_last_index` to **Settings → Energy → Water** for historical water tracking.

## Notes

- SAUR data is typically delayed by 1 day (J-1)
- The integration polls every 4 hours by default (configurable)
- reCAPTCHA: the SAUR mobile API accepts a literal `"true"` token — no browser automation needed
