# SAURon — Session resume guide

> Last updated: 2026-06-16

## Current state

- **Published version on main**: v0.2.2
- **Open PR**: #7 `docs/license-and-readme` — ready to merge → will trigger v0.3.0
- **Working directory**: `C:\SAPDevelop\Git\Personnel\HomeAssistant\projets\ha-sauron`
- **Active branch**: `docs/license-and-readme`

## Sensors — live field readings

| Sensor | Value | Status |
|---|---|---|
| Water index | 470 m³ | ✅ |
| Monthly consumption | 5.15 m³ | ✅ |
| Yearly consumption | 5.92 m³ | ✅ |
| Last reading date | 2026-05-21 | ✅ (billing date) |
| Data age | 0.0 h | ✅ |
| Yesterday consumption (J-1) | Unknown | 🔴 diagnosing |
| Current week consumption | Unknown | 🔴 diagnosing |

## Open diagnostic: weekly endpoint

The weekly coordinator enrichment returns `None` for daily and weekly sensors.
A debug log has been added to `coordinator.py` to capture the raw API response:

```
SAURon weekly raw response for <subscription_id>: <raw_json>
```

**To capture this log:**

1. Add to `configuration.yaml`:
   ```yaml
   logger:
     logs:
       custom_components.sauron: debug
   ```
2. Restart Home Assistant
3. Go to **Settings → System → Logs**, search for `SAURon weekly raw response`
4. Paste the JSON payload here to resume diagnosis

**Expected response shape** (from eyeonsaur-ha reverse engineering):
```json
{
  "consumptions": [
    { "startDate": "2026-06-10 00:00:00", "value": 0.085, "rangeType": "Day" },
    ...
  ]
}
```

If the response is `{"consumptions": []}` or has a different `rangeType`, the parsers
`_extract_daily_liters` and `_extract_week_total_m3` in `coordinator.py` need adapting.

## To resume in Claude Code

Say: **"reprends SAURon — voici le log weekly: [paste log line]"**

Or if diagnosing something else: **"reprends SAURon"** and Claude will read this file.

## Next steps after diagnostic

1. Fix `_extract_daily_liters` / `_extract_week_total_m3` to match real API format
2. Remove the temporary debug log line from `coordinator.py`
3. Merge PR #7 → v0.3.0
4. PR #8 (Silver tier): `diagnostics.py`, `async_migrate_entry` stub, `test_config_flow.py`, `test_init.py`
5. PR #9: Lovelace cards (minimal / mushroom / full blueprints)

## Key files

| File | Purpose |
|---|---|
| `custom_components/sauron/api/client.py` | Auth + all SAUR API endpoints |
| `custom_components/sauron/coordinator.py` | Data fetch + parse helpers |
| `custom_components/sauron/sensor.py` | 7 sensor entities |
| `custom_components/sauron/translations/` | EN/FR/DE/ES i18n |
| `tests/test_coordinator_parse.py` | 41 pure-library tests |

## SAUR API field names (confirmed)

```
POST /admin/v2/auth
  payload: { username, password, client_id: "frontjs-client", grant_type: "password", captchaToken: "true" }
  response: { token: { access_token }, clientId, defaultSectionId }

GET /meter_indexes/last → { readingDate: "ISO", indexValue: float }
GET /consumptions/weekly?year=&month=&day= → { consumptions: [{ startDate, value, rangeType }] }
GET /consumptions/monthly?year=&month= → same structure
GET /consumptions/yearly?year= → same structure
```
