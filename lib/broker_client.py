"""Broker OpenAPI client (order and position operations).

Standard library only (urllib). The API host is never hardcoded: set
``BROKER_API_BASE`` in the env files. Payload field names follow the
broker's REST schema.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple

from lib import env_auth


def _make_req(
    url: str, method: str, headers: dict, payload: dict = None
) -> Tuple[int, dict, dict]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    if payload is not None:
        req.data = json.dumps(payload).encode("utf-8")

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            code = resp.getcode()
            resp_headers = dict(resp.info())
            try:
                data = json.loads(resp.read().decode("utf-8"))
            except Exception:
                data = {}
            return code, data, resp_headers
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {}
        return code, data, dict(e.info())
    except Exception as e:
        return 0, {"error": str(e)}, {}


def _api_base(env: dict) -> str:
    base = (env.get("BROKER_API_BASE") or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("missing BROKER_API_BASE in env")
    return base


def _instrument_id(env: dict) -> int:
    v = env.get("INSTRUMENT_ID")
    if not v:
        raise RuntimeError("missing INSTRUMENT_ID in env")
    return int(v)


def _token_or_load(token: str | None) -> str:
    if token:
        return token
    env_token = os.environ.get("BROKER_TOKEN", "")
    if env_token:
        return env_token
    from lib import token_io

    return token_io.get_access_token()


def get_lot_size() -> int:
    env = env_auth.load_trade_env()
    return int(env.get("LOT_SIZE", "10000"))


def lots_to_units(lots: float) -> int:
    return int(round(lots * get_lot_size()))


def place_market_order(
    token: str, lots: float, side: str, account_key: str, manual_order: bool = False
) -> Tuple[int, Dict[str, Any]]:
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    instrument_id = _instrument_id(env)
    asset_type = env.get("ASSET_TYPE", "FxSpot")
    if lots <= 0:
        raise ValueError(f"Invalid lots: {lots}")
    amount = lots_to_units(lots)
    if amount <= 0:
        raise ValueError(f"Invalid amount: {amount}")
    url = f"{api_base}/trade/v2/orders"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    buysell = "Buy" if side.upper() in ("BUY", "LONG") else "Sell"
    payload = {
        "AccountKey": account_key,
        "Amount": amount,
        "AssetType": asset_type,
        "BuySell": buysell,
        "ManualOrder": manual_order,
        "OrderDuration": {"DurationType": "DayOrder"},
        "OrderType": "Market",
        "Uic": instrument_id,
    }
    code, data, _ = _make_req(url, "POST", headers, payload)
    return code, data


def get_net_position_qty(token: str) -> float:
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    account_key = env.get("ACCOUNT_KEY")
    instrument_id = _instrument_id(env)
    url = (
        f"{api_base}/port/v1/netpositions/me?AccountKey={account_key}"
        f"&FieldGroups=NetPositionBase,NetPositionView&Uic={instrument_id}"
    )
    headers = {"Authorization": f"Bearer {token}"}
    code, data, _ = _make_req(url, "GET", headers)
    if code != 200:
        return 0.0
    for pos in (data or {}).get("Data", []):
        base = pos.get("NetPositionBase") or {}
        pos_id = base.get("Uic")
        if pos_id is not None and int(pos_id) == instrument_id:
            amount = base.get("Amount")
            direction = base.get("OpeningDirection")
            if amount is not None and direction:
                amt = abs(float(amount))
                if direction == "Sell":
                    amt = -amt
                return amt
    return 0.0


def get_price(
    account_key: str, instrument_id: int, asset_type: str
) -> Tuple[int, str, Dict[str, Any]]:
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    token = _token_or_load(None)
    url = (
        f"{api_base}/trade/v1/infoprices?Uic={instrument_id}&AssetType={asset_type}"
        f"&AccountKey={account_key}&FieldGroups=Quote"
    )
    headers = {"Authorization": f"Bearer {token}"}
    code, data, resp_headers = _make_req(url, "GET", headers)
    return code, resp_headers.get("X-Correlation", ""), data


def cancel_order(
    order_id: str, instrument_id: int, reason: str = ""
) -> Tuple[int, str, Dict[str, Any]]:
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    account_key = env.get("ACCOUNT_KEY", "")
    token = _token_or_load(None)
    url = f"{api_base}/trade/v2/orders/{order_id}?AccountKey={account_key}"
    headers = {"Authorization": f"Bearer {token}"}
    code, data, resp_headers = _make_req(url, "DELETE", headers)
    return code, resp_headers.get("X-Correlation", ""), data


def list_open_orders(token=None):
    token = _token_or_load(token)
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    account_key = env.get("ACCOUNT_KEY")
    url = (
        f"{api_base}/port/v1/orders/me?AccountKey={account_key}"
        f"&Status=Working&FieldGroups=DisplayAndFormat,ExchangeInfo"
    )
    headers = {"Authorization": f"Bearer {token}"}
    code, data, _ = _make_req(url, "GET", headers)
    if code != 200:
        return {"Data": [], "error": f"HTTP {code}"}
    return data


def get_netposition(token, instrument_id):
    token = _token_or_load(token)
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    account_key = env.get("ACCOUNT_KEY")
    url = (
        f"{api_base}/port/v1/netpositions/me?AccountKey={account_key}"
        f"&FieldGroups=NetPositionBase,NetPositionView&Uic={instrument_id}"
    )
    headers = {"Authorization": f"Bearer {token}"}
    _, data, _ = _make_req(url, "GET", headers)
    return data


def get_netpositions_me(token=None):
    token = _token_or_load(token)
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    account_key = env.get("ACCOUNT_KEY")
    url = (
        f"{api_base}/port/v1/netpositions/me?AccountKey={account_key}"
        f"&FieldGroups=NetPositionBase,NetPositionView"
    )
    headers = {"Authorization": f"Bearer {token}"}
    _, data, _ = _make_req(url, "GET", headers)
    return data


def _place_bracket(order_type, account_key, instrument_id, asset_type, side, amount, price, ext_ref):
    token = _token_or_load(None)
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    url = f"{api_base}/trade/v2/orders"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "AccountKey": account_key,
        "Amount": amount,
        "AssetType": asset_type,
        "BuySell": side,
        "OrderType": order_type,
        "OrderPrice": price,
        "OrderDuration": {"DurationType": "GoodTillCancel"},
        "Uic": instrument_id,
        "ExternalReference": ext_ref,
        "ManualOrder": False,
    }
    code, data, resp_headers = _make_req(url, "POST", headers, payload)
    return code, resp_headers.get("X-Correlation", ""), data


def place_limit(account_key, instrument_id, asset_type, side, amount, price, ext_ref):
    return _place_bracket("Limit", account_key, instrument_id, asset_type, side, amount, price, ext_ref)


def place_stop(account_key, instrument_id, asset_type, side, amount, price, ext_ref):
    return _place_bracket("Stop", account_key, instrument_id, asset_type, side, amount, price, ext_ref)


def get_positions_me(token=None):
    token = _token_or_load(token)
    env = env_auth.load_trade_env()
    api_base = _api_base(env)
    account_key = env.get("ACCOUNT_KEY")
    url = f"{api_base}/port/v1/positions/me?AccountKey={account_key}"
    headers = {"Authorization": f"Bearer {token}"}
    _, data, _ = _make_req(url, "GET", headers)
    return data
