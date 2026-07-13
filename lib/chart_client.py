"""Chart-data client used by ``fetch_bars``.

Reads the shared token file and pulls OHLC bars from the broker's chart
endpoint. Host comes from ``BROKER_API_BASE``; nothing is hardcoded.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _load_live_token():
    env_path = os.environ.get("BROKER_TOKEN_FILE") or os.environ.get("TOKEN_FILE")
    if env_path:
        path = Path(env_path)
    else:
        base = os.environ.get("MARKET_DATA") or os.path.expanduser("~/market_data")
        path = Path(base) / "state" / "tokens" / "live_current.json"

    if path.is_file():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError(f"live_current.json not found at: {path}")


class ChartClient:
    def __init__(self, base_url=None, token=None, timeout=5.0):
        if base_url is None:
            base_url = os.environ.get("BROKER_API_BASE")
        if not base_url:
            raise RuntimeError("missing BROKER_API_BASE in env")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token or _load_live_token()
        self._auth_header = ""
        self.set_token(self.token)

    def set_token(self, token):
        access_token = token.get("access_token")
        if not access_token:
            raise RuntimeError("missing_access_token")
        token_type = token.get("token_type") or "Bearer"
        self.token = token
        self._auth_header = f"{token_type} {access_token}"

    def _reload_token(self):
        self.set_token(_load_live_token())

    def _get(self, path, params=None):
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        for attempt in range(2):
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", self._auth_header)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    self._reload_token()
                    continue
                return {}
            except Exception:
                return {}
        return {}

    def get_chart_data(self, instrument_id, time_spec, count=None, horizon=1):
        params = {
            "AssetType": os.environ.get("ASSET_TYPE", "FxSpot"),
            "Uic": instrument_id,
            "Horizon": horizon,
            "Mode": "From",
            "Time": time_spec,
        }
        if count:
            params["Count"] = count
        res = self._get("/chart/v3/charts", params)
        if isinstance(res, dict) and "Data" in res:
            return res.get("Data")
        return []
