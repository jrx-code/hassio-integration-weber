"""Resolve the app-embedded OAuth client credentials.

They are not shipped in the repo. Resolution order:
  1. environment variables WEBER_CLIENT_ID / WEBER_CLIENT_SECRET
  2. a `weber_june.env` file in the HA config dir (KEY=VALUE), for HAOS installs
     where injecting env into the core process is not user-serviceable.
"""
from __future__ import annotations

import os


def resolve_client_credentials(config_dir: str) -> tuple[str, str]:
    cid = os.environ.get("WEBER_CLIENT_ID", "").strip()
    csec = os.environ.get("WEBER_CLIENT_SECRET", "").strip()
    if cid and csec:
        return cid, csec
    path = os.path.join(config_dir, "weber_june.env")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                if key.strip() == "WEBER_CLIENT_ID" and not cid:
                    cid = val
                elif key.strip() == "WEBER_CLIENT_SECRET" and not csec:
                    csec = val
    except OSError:
        pass
    return cid, csec
