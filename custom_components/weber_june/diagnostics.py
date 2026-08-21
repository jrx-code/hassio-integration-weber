"""Diagnostics for Weber Connect.

Dumps the raw cloud payloads next to what the client decoded from them, so
fields the integration ignores are visible rather than silently dropped.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_APPLIANCE_ID, CONF_COMPANION_ID, CONF_REFRESH_TOKEN

REDACT = {CONF_REFRESH_TOKEN, CONF_APPLIANCE_ID, CONF_COMPANION_ID}
# Ids that also appear inside the raw payloads, where async_redact_data on the
# entry alone would not reach them.
REDACT_RAW = {"appliance_id", "session_id", "serial_number"}
# Field 0x08 of a companion frame is the session uuid; the frame header carries
# the appliance and companion uuids. Diagnostics get attached to public issues,
# so none of them may be dumped verbatim.
REDACT_FRAME_FIELDS = {"0x08"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    client = coordinator.client
    frame = client.last_frame_raw

    details = asdict(coordinator.details)
    if details.get("serial_number"):
        details["serial_number"] = "**REDACTED**"

    fields = client.frame_inventory(frame) if frame else []
    for f in fields:
        if f.get("field") in REDACT_FRAME_FIELDS:
            f["hex"] = "**REDACTED**"
        for sub in f.get("sub") or []:
            # The probe id is a uuid too; its length gives it away.
            if sub.get("len") == 16:
                sub["hex"] = "**REDACTED**"

    return {
        "entry_data": async_redact_data(dict(entry.data), REDACT),
        "appliance_details": details,
        "decoded_state": async_redact_data(
            asdict(coordinator.data) if coordinator.data else {}, REDACT_RAW
        ),
        "rest_snapshot_raw": async_redact_data(
            client.last_snapshot_raw or {}, REDACT_RAW
        ),
        "ws_frame": {
            "length": len(frame) if frame else 0,
            # Header holds the appliance and companion uuids — length only.
            "header_len": 34 if frame else 0,
            "fields": fields,
        },
    }
