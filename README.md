# Weber Connect — Home Assistant integration

Read the live state of a WiFi-connected **Weber Connect** grill (Spirit / June) in Home
Assistant, **straight from the cloud, with no companion app or Android VM running**.

The grill talks to `walker-cloud.com` over its own WiFi. This integration reuses
the same cloud API the official *Weber Connect* app uses — reverse-engineered and
reimplemented with **zero external dependencies** (Python stdlib only).

## Screenshots

| Device & entities | Setup |
|---|---|
| ![Device page](images/device.png) | ![Config flow](images/config-flow.png) |

## Entities

| Entity | Source |
|---|---|
| Cavity temperature | cook-history REST |
| Cavity target (setpoint) | companion WebSocket |
| Probe temperature(s) | cook-history REST / WebSocket |
| Connection | messaging `/status` |
| Mode | companion WebSocket (raw, see table below) |

Device name, model and serial number come from the cloud when a *Companion id*
is configured (see below); otherwise generic values are used.

## What it is — and isn't

- ✅ **App-free**: mints its own access token from a long-lived refresh token and
  reads temperatures + setpoint directly from the cloud.
- ⚠️ **Read-only**: it reads the grill's state; it cannot *set* the target from HA
  (the command channel is not implemented). Use an `input_number` + an automation
  if you want an HA-owned target/alarm.
- ⚠️ **Probe target is not on the cloud** — the cloud carries the probe
  *temperature* but not its setpoint, so there is no probe-target entity.
- ⚠️ **One session per account**: the live stream is a single connection, so this
  integration and the official app **cannot both run** at the same time. Use one
  or the other.

## Configuration

### OAuth client credentials (one-time, per install)

The OAuth *client* credentials (the same for every user, embedded in the Weber
Connect APK) are **not shipped in this repo**. Provide them once via the
environment of the process running Home Assistant, either way:

- **Environment variables** — `WEBER_CLIENT_ID` and `WEBER_CLIENT_SECRET`
  (Container/Supervised: `-e …`; Core venv/systemd: `Environment=` / `export`).
- **File fallback (HAOS)** — HAOS does not let you set env on the core process, so
  drop a `weber_june.env` in your HA config directory instead:

  ```
  WEBER_CLIENT_ID=...
  WEBER_CLIENT_SECRET=...
  ```

Extract the two values from a Weber Connect APK
(`com.weber.config.WalkerProdConfig`). See [.env.example](.env.example).

### Account

The only per-user secret is your account **refresh token**. The appliance id is
detected automatically while the grill is powered on (or you can type it in).

### Getting the refresh token

The token lives in the Weber Connect app's SQLite database on a device where you
are logged in:

```
com.weber.connect/databases/june_sdk.db   →   table session_info_table
  column: refresh_token   (value like "v2:...")
```

Read it with its `-wal` sidecar (a just-refreshed value lands there first). This
requires adb/root access to the device running the app — an advanced, one-time
step.

**The refresh token rotates.** The cloud can hand back a new one on any mint and
retire the old, so the integration writes each new value back into the config
entry. If the stored token is ever rejected anyway, the entry raises a **reauth**
prompt: paste a current token and the grill, its entities and their history are
kept. To obtain a fresh token, open the Weber Connect app on a device you own —
it re-registers itself and writes a new row into `session_info_table`.

### Appliance model and serial (optional)

Leave *Companion id* empty and the device shows generic info. Fill it in and the
integration reads the appliance name, model number and serial number from
`GET /2/devices/{companionId}/associated`. The companion id identifies the app
registration your token belongs to; it sits next to the token, in
`june_sdk.db` → `companion_info_table` → `companion_id`. An existing entry can
gain one later via *Reconfigure* — no need to delete and re-add it.

## Cook modes

`Mode` is reported as the raw protocol value:

| Value | Cloud name | Constant |
|---|---|---|
| 0 | `unknown` | `NONE` |
| 1 | `grill` | `GRILL` |
| 2 | `smoke_boost` | `SMOKE` |
| 3 | `preheat` | `OBSERVER` |
| 4 | `indirect` | `INDIRECT` |
| 5 | `custom` | `CUSTOM` |
| 6 | `simple` | `SIMPLE_INTENSITY` |
| 7 | `manual` | `MANUAL` |
| 8 | `sear` | `SEAR` |
| 9 | `steam` | `STEAM` |
| 10 | `warm` | `WARM` |

## Diagnostics

*Settings → Devices & Services → Weber Connect → ⋮ → Download diagnostics* dumps
the raw REST snapshot and a full field inventory of the last companion frame —
including fields the integration does not decode — next to the decoded state.
Appliance, session and probe identifiers are redacted.

## Install (HACS)

1. HACS → Integrations → ⋮ → *Custom repositories* → add this repo (category:
   *Integration*).
2. Install **Weber Connect**, restart Home Assistant.
3. *Settings → Devices & Services → Add Integration → Weber Connect* and
   paste the refresh token.

## License

MIT — see [LICENSE](LICENSE).

> Not affiliated with or endorsed by Weber-Stephen Products LLC. "Weber" and
> "Spirit" are trademarks of their respective owners. Uses undocumented cloud
> endpoints that may change at any time.
