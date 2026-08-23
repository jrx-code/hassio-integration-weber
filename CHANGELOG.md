# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-08-23

Packaging only — no functional change to the integration.

### Changed
- HACS validation now runs the `brands` check as well; it passes on the brand
  assets shipped in `custom_components/weber_june/brand/`.
- README carries install instructions for HACS and manual installs, plus
  My Home Assistant links for adding the repository and starting the config flow.

### Removed
- `info.md`. HACS 2.x renders the README and no longer reads an info file, so the
  file was a second copy of the description that nothing displayed.

## [0.2.0] - 2026-08-21

### Added
- **Reauth flow.** A retired refresh token raises `ConfigEntryAuthFailed` and Home
  Assistant prompts for a new one; the entry, its entities and their history survive.
- Appliance name, model number and serial number read from the cloud when an
  optional *Companion id* is configured, with a **Reconfigure** step so an
  existing entry can gain one without being deleted.
- Diagnostics download: the raw REST snapshot plus a full field inventory of the
  last companion frame, including fields the integration does not decode.
  Appliance, session and probe identifiers are redacted, also inside raw payloads.
- Brand assets under `custom_components/weber_june/brand/`.
- Cook-mode table in the README (raw protocol values 0–10).

### Changed
- Renamed to **Weber Connect** in the UI. The domain stays `weber_june`, so
  existing entries and entity ids are untouched.
- A rotated refresh token is now written back into the config entry. Previously it
  only lived in the client, so a restart fell back to a token the cloud had
  already retired.

## [0.1.0] - 2026-08-21

First release.

### Added
- Cloud-only, app-free reading of a WiFi Weber Connect grill (Spirit / June):
  cavity temperature and target, probe temperature, connection and cook mode.
- Config flow taking the account refresh token, with automatic appliance-id
  detection while the grill is powered on.
- OAuth client credentials read from the environment or from a `weber_june.env`
  file in the config directory, so they are never committed to this repository.
- Zero external dependencies — Python standard library only.

[0.2.1]: https://github.com/jrx-code/hassio-integration-weber/releases/tag/v0.2.1
[0.2.0]: https://github.com/jrx-code/hassio-integration-weber/releases/tag/v0.2.0
[0.1.0]: https://github.com/jrx-code/hassio-integration-weber/releases/tag/v0.1.0
