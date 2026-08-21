"""Constants for the Weber Spirit / June cloud integration."""

import os

DOMAIN = "weber_june"

# Cloud endpoints (June / walker-cloud). Same hosts the official app uses.
API_BASE = "https://api.walker-cloud.com"
MESSAGING_BASE = "https://messaging.walker-cloud.com"
AUTH_PATH = "/2/auth/oauth/token"
WS_HOST = "messaging.walker-cloud.com"
WS_PATH = "/2/messaging/websocket/companion"
UA = "okhttp/5.3.0"

# OAuth *client* credentials for the June/walker cloud. These are embedded in the
# Weber Connect APK (com.weber.config.WalkerProdConfig), identical for every
# install and recoverable from the public APK — app configuration, not a per-user
# secret. They are NOT shipped in this repo: supply them via the environment of
# the process running Home Assistant (see .env.example). The per-user secret is
# the refresh token, supplied at config time.
CLIENT_ID = os.environ.get("WEBER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("WEBER_CLIENT_SECRET", "")

# Temperatures are little-endian deci-degrees Celsius on the wire.
DECI = 10.0

# Refresh the access token this many seconds before it expires.
TOKEN_SKEW = 300.0

CONF_REFRESH_TOKEN = "refresh_token"
CONF_APPLIANCE_ID = "appliance_id"

DEFAULT_SCAN_INTERVAL = 30

MANUFACTURER = "Weber"
