"""Read-side of OCO management: our working orders and the net position."""
from __future__ import annotations

import time

from lib import broker_client as bc


def list_orders(instrument_id):
    j = bc.list_open_orders(None)
    d = (j or {}).get("Data") or []
    r = []
    for o in d:
        try:
            if int(o.get("Uic", 0)) != int(instrument_id):
                continue

            sl = o.get("SingleLegOrder") or {}
            order_type = sl.get("OrderType") or o.get("OpenOrderType") or ""
            amount = sl.get("Amount") or o.get("Amount") or 0
            price = sl.get("Price") or o.get("Price") or 0
            side = sl.get("BuySell") or o.get("BuySell") or ""

            if order_type in ("StopIfTraded",):
                order_type = "Stop"
            if order_type not in ("Limit", "Stop"):
                continue

            r.append(
                {
                    "id": o.get("OrderId"),
                    "type": order_type,
                    "side": side,
                    "amt": int(float(amount)),
                    "price": float(price),
                    "ext": str(o.get("ExternalReference") or ""),
                    "status": o.get("Status"),
                }
            )
        except Exception:
            pass
    return r


def _extract_net_from_item(item):
    if not isinstance(item, dict):
        return 0.0, 0.0

    base = item.get("NetPositionBase") or {}
    view = item.get("NetPositionView") or {}

    avg = 0.0
    try:
        avg = float(view.get("AverageOpenPrice") or 0)
    except Exception:
        pass

    amount = base.get("Amount")
    if amount is not None:
        try:
            return float(amount), avg
        except Exception:
            pass

    exposure = view.get("Exposure")
    if exposure is not None:
        try:
            return float(exposure), avg
        except Exception:
            pass

    return 0.0, avg


def get_net(instrument_id):
    for _ in range(5):
        j = bc.get_netposition(None, instrument_id)
        d = (j or {}).get("Data") or []
        for item in d:
            net, avg = _extract_net_from_item(item)
            if net != 0:
                return net, avg
        if d:
            return 0.0, 0.0
        time.sleep(0.3)

    j = bc.get_netpositions_me()
    d = (j or {}).get("Data") or []
    for item in d:
        item_base = item.get("NetPositionBase") or {}
        item_uic = item_base.get("Uic")
        if item_uic is None:
            continue
        try:
            if int(item_uic) != int(instrument_id):
                continue
        except Exception:
            continue
        net, avg = _extract_net_from_item(item)
        if net != 0:
            return net, avg

    return 0.0, 0.0
