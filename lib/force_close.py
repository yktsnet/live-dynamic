"""Force-close every open position and cancel our bracket orders.

Shared by the EOD close and the kill-switch check. Raises ``NoPos`` when
there is nothing to close so callers can treat that as success.
"""
from __future__ import annotations

import time

from lib import broker_client, env_auth, token_io


def _cancel_bracket_orders(token: str, instrument_id: int) -> None:
    orders_data = broker_client.list_open_orders(token)
    for order in (orders_data or {}).get("Data", []):
        if int(order.get("Uic", 0)) != instrument_id:
            continue
        if order.get("OpenOrderType") not in ("Limit", "StopIfTraded", "Stop"):
            continue
        order_id = str(order.get("OrderId", ""))
        if not order_id:
            continue
        broker_client.cancel_order(order_id, instrument_id)
    time.sleep(0.5)


def close_all_positions() -> None:
    token = token_io.get_access_token()
    env = env_auth.load_trade_env()
    account_key = env.get("ACCOUNT_KEY")
    instrument_id = int(env["INSTRUMENT_ID"])

    data = broker_client.get_netpositions_me(token)
    positions = data.get("Data", [])

    if not positions:
        raise Exception("NoPos")

    _cancel_bracket_orders(token, instrument_id)

    errors = []
    lot_size = broker_client.get_lot_size()

    for pos in positions:
        net_base = pos.get("NetPositionBase", {})
        amount = float(net_base.get("Amount", 0))

        if amount == 0:
            continue

        side = "Sell" if amount > 0 else "Buy"
        lots = abs(amount) / lot_size

        code, resp = broker_client.place_market_order(token, lots, side, account_key)
        if code not in (200, 201):
            errors.append(f"HTTP {code}: {resp}")

    if errors:
        raise Exception(f"CloseErrors: {', '.join(errors)}")
