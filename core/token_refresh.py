"""Refresh the broker access token.

Runs every 5 minutes from a systemd timer. The refresh token is rotated in
place; if the broker does not return a new one, the old one is kept.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from lib import env_auth, token_io


def main() -> int:
    oc = env_auth.load_trade_env()
    client_id = oc.get("BROKER_CLIENT_ID")
    auth_base = (oc.get("BROKER_AUTH_BASE") or "").strip().rstrip("/")

    if not client_id:
        print("[error] missing BROKER_CLIENT_ID in env", file=sys.stderr)
        return 2
    if not auth_base:
        print("[error] missing BROKER_AUTH_BASE in env", file=sys.stderr)
        return 3

    t = token_io.load_token()
    ref_old = (t.get("refresh_token") or "").strip()
    if not ref_old:
        print("[error] missing refresh_token", file=sys.stderr)
        return 4

    url = auth_base + "/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": ref_old,
        "client_id": client_id,
    }
    try:
        req_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url=url, data=body, headers=req_headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            newt = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[error] refresh failed: {e}", file=sys.stderr)
        return 5

    if not newt.get("refresh_token"):
        newt["refresh_token"] = ref_old

    ei = newt.get("expires_in")
    if isinstance(ei, (int, float)):
        newt["_access_expires_at"] = int(time.time()) + int(ei)
        newt["access_expires_at"] = datetime.fromtimestamp(
            newt["_access_expires_at"], tz=timezone.utc
        ).isoformat()

    token_io.save_token(newt)
    print(f"token refreshed; access_expires_at(UTC)={newt.get('access_expires_at', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
