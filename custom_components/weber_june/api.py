"""App-free client for Weber Spirit / June grills over the walker-cloud API.

Dependency-free (stdlib only). Three cloud facts make it work, all reverse-
engineered from the official app and replayed without it:

  * Auth: GET /2/auth/oauth/token?grant_type=refresh_token mints a short-lived
    access token from a long-lived (non-rotating) refresh token. The refresh
    token is the one secret the user supplies.
  * Telemetry: GET /cook-history/1/appliance/<id>/session/<sid>/snapshots streams
    cavity/probe temperatures (deci-°C).
  * Setpoint: the companion WebSocket
    (wss://messaging.walker-cloud.com/2/messaging/websocket/companion) pushes a
    plaintext binary status frame carrying the cavity target (and temps/mode).

The companion stream is one connection per account, so the official app and this
client cannot both run — this is a cloud reader for when the app is not in use.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import socket
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from .const import (
    API_BASE,
    AUTH_PATH,
    CLIENT_ID,
    CLIENT_SECRET,
    DECI,
    MESSAGING_BASE,
    TOKEN_SKEW,
    UA,
    WS_HOST,
    WS_PATH,
)


class WeberAuthError(Exception):
    """Refresh token rejected / cannot mint an access token."""


class WeberClientCredentialsError(Exception):
    """The app-embedded OAuth client credentials are not configured."""


class WeberConnectionError(Exception):
    """Transient network/HTTP failure talking to the cloud."""


@dataclass
class GrillState:
    online: bool = False
    cavity_temp_c: Optional[float] = None
    cavity_target_c: Optional[float] = None
    probe_temps_c: list[float] = field(default_factory=list)
    mode: Optional[int] = None
    session_id: Optional[str] = None


class WeberJuneClient:
    """Holds the token + snapshot cursor across polls. All calls are blocking."""

    def __init__(self, refresh_token: str, appliance_id: str = "",
                 client_id: str = CLIENT_ID, client_secret: str = CLIENT_SECRET):
        self._refresh = refresh_token
        self.appliance_id = appliance_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: Optional[str] = None
        self._token_exp: float = 0.0
        self._session: Optional[str] = None
        self._after_id = 0

    # -- auth -------------------------------------------------------------
    def ensure_token(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._token_exp - TOKEN_SKEW:
            return self._token
        if not self._client_id or not self._client_secret:
            raise WeberClientCredentialsError(
                "WEBER_CLIENT_ID / WEBER_CLIENT_SECRET are not set in the "
                "environment of the Home Assistant process")
        q = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self._refresh,
            "client_secret": self._client_secret,
            "client_id": self._client_id,
        })
        req = urllib.request.Request(
            f"{API_BASE}{AUTH_PATH}?{q}",
            headers={"User-Agent": UA, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise WeberAuthError(f"token refresh HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise WeberConnectionError(str(e)) from e
        tok = d.get("access_token")
        if not tok:
            raise WeberAuthError("no access_token in refresh response")
        self._token = tok
        if d.get("refresh_token"):
            self._refresh = d["refresh_token"]
        self._token_exp = time.time() + float(d.get("expires_in") or 0)
        return self._token

    @property
    def refresh_token(self) -> str:
        return self._refresh

    # -- REST -------------------------------------------------------------
    def _get(self, url: str) -> tuple[int, object]:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._token}",
            "User-Agent": UA, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return r.status, json.loads(raw.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            return e.code, None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise WeberConnectionError(str(e)) from e

    def _get_retrying(self, url: str) -> tuple[int, object]:
        self.ensure_token()
        code, body = self._get(url)
        if code == 401:
            self.ensure_token(force=True)
            code, body = self._get(url)
        return code, body

    def online(self) -> bool:
        code, body = self._get_retrying(
            f"{MESSAGING_BASE}/1/messaging/device/{self.appliance_id}/status")
        return code == 200 and isinstance(body, dict) \
            and body.get("connection_state") == "online"

    def _current_session(self) -> Optional[str]:
        code, body = self._get_retrying(
            f"{API_BASE}/cook-history/1/appliance/{self.appliance_id}"
            f"/sessions?limit=1000")
        if code != 200 or not isinstance(body, list) or not body:
            return None
        return max(body, key=lambda s: s.get("boot_count", 0)).get("session_id")

    def _latest_snapshot(self, session: str) -> Optional[dict]:
        last = None
        for _ in range(50):
            code, body = self._get_retrying(
                f"{API_BASE}/cook-history/1/appliance/{self.appliance_id}"
                f"/session/{session}/snapshots?limit=1000&after_id={self._after_id}")
            if code != 200 or not isinstance(body, dict):
                break
            snaps = body.get("snapshots") or []
            if not snaps:
                break
            last = snaps[-1]
            self._after_id = last.get("snapshot_id", self._after_id)
            if len(snaps) < 1000:
                break
        return last

    @staticmethod
    def _temp(entries) -> Optional[float]:
        if entries and isinstance(entries, list):
            t = entries[0].get("temperature")
            return round(t / DECI, 1) if t is not None else None
        return None

    # -- companion WebSocket (setpoint) -----------------------------------
    def read_ws_frame(self, timeout: float = 8.0) -> Optional[bytes]:
        """Open the companion WS, return one binary status frame (or None)."""
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {WS_PATH} HTTP/1.1\r\nHost: {WS_HOST}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            f"Authorization: Bearer {self._token}\r\nUser-Agent: {UA}\r\n\r\n"
        )
        ctx = ssl.create_default_context()
        try:
            s = ctx.wrap_socket(socket.create_connection((WS_HOST, 443), timeout=timeout),
                                server_hostname=WS_HOST)
        except OSError as e:
            raise WeberConnectionError(str(e)) from e
        s.settimeout(timeout)
        try:
            s.sendall(req.encode())
            buf = b""
            while b"\r\n\r\n" not in buf:
                d = s.recv(4096)
                if not d:
                    return None
                buf += d
            if b" 101 " not in buf.split(b"\r\n", 1)[0]:
                return None
            rest = buf.partition(b"\r\n\r\n")[2]

            def need(n, cur):
                while len(cur) < n:
                    d = s.recv(4096)
                    if not d:
                        raise WeberConnectionError("closed mid-frame")
                    cur += d
                return cur

            rest = need(2, rest)
            opcode = rest[0] & 0x0F
            ln = rest[1] & 0x7F
            off = 2
            if ln == 126:
                rest = need(4, rest); ln = struct.unpack(">H", rest[2:4])[0]; off = 4
            elif ln == 127:
                rest = need(10, rest); ln = struct.unpack(">Q", rest[2:10])[0]; off = 10
            rest = need(off + ln, rest)
            if opcode != 0x02:
                return None
            return rest[off:off + ln]
        except (OSError, ValueError) as e:
            raise WeberConnectionError(str(e)) from e
        finally:
            try:
                s.close()
            except OSError:
                pass

    @staticmethod
    def _parse_frame(frame: bytes) -> dict:
        """Parse cavity target/temp, probe temp, mode from a companion frame."""
        out: dict = {}
        idx = frame.find(b"\x80", 34)
        if idx < 0:
            return out
        body = frame[idx + 1:]
        j = 0
        while j + 2 <= len(body):
            f, ln = body[j], body[j + 1]
            val = body[j + 2:j + 2 + ln]
            if j + 2 + ln > len(body):
                break
            if f == 0x01 and ln == 2:
                t = int.from_bytes(val, "little") / DECI
                if 0 < t < 400:
                    out["cavity_target_c"] = round(t, 1)
            elif f == 0x02 and ln == 2:
                out["cavity_temp_c"] = round(int.from_bytes(val, "little") / DECI, 1)
            elif f == 0x03 and ln == 1:
                out["mode"] = val[0]
            elif f == 0x04:                       # probe sub-block
                k = 0
                while k + 2 <= len(val):
                    pf, pln = val[k], val[k + 1]
                    pv = val[k + 2:k + 2 + pln]
                    if k + 2 + pln > len(val):
                        break
                    if pf == 0x0A and pln == 2:
                        out["probe_temp_c"] = round(int.from_bytes(pv, "little") / DECI, 1)
                    k += 2 + pln
            j += 2 + ln
        return out

    # -- discovery + poll -------------------------------------------------
    def discover_appliance_id(self, attempts: int = 3) -> Optional[str]:
        """Read the appliance id from a companion frame (frame[2:18]).

        Best-effort: the stream only pushes while the grill is powered/active, so
        this can legitimately fail — callers should fall back to manual entry.
        """
        self.ensure_token()
        for _ in range(max(1, attempts)):
            try:
                frame = self.read_ws_frame()
            except WeberConnectionError:
                frame = None
            if frame and len(frame) >= 18 and frame[0:2] == b"\x01\x01":
                return frame[2:18].hex()
        return None

    def poll(self) -> GrillState:
        """One update: online + temps (REST) + setpoint/mode (WS)."""
        self.ensure_token()
        st = GrillState(online=self.online())

        if self._session is None:
            self._session = self._current_session()
            self._after_id = 0
        if self._session:
            st.session_id = self._session
            snap = self._latest_snapshot(self._session)
            if snap is None and st.online:
                new = self._current_session()
                if new and new != self._session:
                    self._session = new
                    self._after_id = 0
                    snap = self._latest_snapshot(self._session)
            if snap:
                data = snap.get("data", {})
                st.cavity_temp_c = self._temp(data.get("cavity_status"))
                st.probe_temps_c = [
                    round(p["temperature"] / DECI, 1)
                    for p in (data.get("probe_status") or [])
                    if p.get("temperature") is not None
                ]

        # Setpoint + mode (+ temp fallback) from the companion WS. Best-effort:
        # a failure here must not drop the REST telemetry.
        try:
            frame = self.read_ws_frame()
        except WeberConnectionError:
            frame = None
        if frame:
            f = self._parse_frame(frame)
            st.cavity_target_c = f.get("cavity_target_c")
            if st.cavity_temp_c is None:
                st.cavity_temp_c = f.get("cavity_temp_c")
            if f.get("mode") is not None:
                st.mode = f["mode"]
            if not st.probe_temps_c and f.get("probe_temp_c") is not None:
                st.probe_temps_c = [f["probe_temp_c"]]
        return st
