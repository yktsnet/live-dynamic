"""OCO management: keep exactly one TP Limit and one SL Stop bracketing the
current net position, cancelling stale or orphaned brackets first."""
from __future__ import annotations

import os
import time
from lib import broker_client as bc
from lib import oco_env as oe
from lib import oco_repo as repo


def _acct():
    v = os.environ.get("ACCOUNT_KEY") or os.environ.get("AccountKey") or ""
    if v:
        return v
    try:
        from lib import env_auth
        cfg = env_auth.load_trade_env()
        return cfg.get("ACCOUNT_KEY", "")
    except Exception:
        return ""


def _cancel_stale_orders(instrument_id, existing, amt, extp, exts):
    cancelled = 0
    for o in existing:
        is_our_tp = o["type"] == "Limit" and extp in o["ext"]
        is_our_sl = o["type"] == "Stop" and exts in o["ext"]
        if not (is_our_tp or is_our_sl):
            continue
        if amt > 0 and o["amt"] == amt:
            continue
        oid = o.get("id")
        if not oid:
            continue
        try:
            rc, _, _ = bc.cancel_order(str(oid), int(instrument_id), reason="stale_oco_amt_mismatch")
            if int(rc) in (200, 202, 204):
                cancelled += 1
                print(f"oco_manager: cancelled stale order {oid} (amt={o['amt']} != net={amt})")
            else:
                print(f"oco_manager: cancel failed order {oid} rc={rc}")
        except Exception as e:
            print(f"oco_manager: cancel error order {oid}: {e}")
    return cancelled


def _cancel_all_oco_orders(instrument_id, extp, exts):
    j = bc.list_open_orders(None)
    d = (j or {}).get("Data") or []
    cancelled = 0
    for o in d:
        try:
            if int(o.get("Uic", 0)) != int(instrument_id):
                continue
        except Exception:
            continue
        ext = str(o.get("ExternalReference") or "")
        if extp not in ext and exts not in ext:
            continue
        oid = o.get("OrderId")
        if not oid:
            continue
        try:
            rc, _, _ = bc.cancel_order(str(oid), int(instrument_id), reason="no_net_cleanup")
            if int(rc) in (200, 202, 204):
                cancelled += 1
                print(f"oco_manager: cancelled orphan order {oid} (no net position)")
            else:
                print(f"oco_manager: cancel orphan failed {oid} rc={rc}")
        except Exception as e:
            print(f"oco_manager: cancel orphan error {oid}: {e}")
        time.sleep(0.3)
    return cancelled


def _place_with_429_retry(place_fn, acct, instrument_id, asset_type, side, amt, price, ext_ref, max_retries=3):
    for attempt in range(max_retries + 1):
        rc, cid, body = place_fn(acct, instrument_id, asset_type, side, amt, price, ext_ref)
        if int(rc) in (200, 201):
            return rc, cid, body
        if int(rc) == 429:
            if attempt < max_retries:
                wait = 1.0 + attempt * 0.5
                print(f"oco_manager: 429 rate limit, waiting {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            else:
                print(f"oco_manager: 429 rate limit, giving up after {max_retries} retries")
                return rc, cid, body
        return rc, cid, body
    return rc, cid, body


def ensure(instrument_id=None, asset_type=None):
    instrument_id = int(instrument_id or oe.env_int("INSTRUMENT_ID", 0))
    if not instrument_id:
        print("oco_manager: ERROR no INSTRUMENT_ID in env")
        return {"status": "error", "reason": "no_instrument_id"}
    asset_type = asset_type or oe.env_str("ASSET_TYPE", "FxSpot")
    tp_pips = oe.env_int("RR_PIPS_TP", 30)
    sl_pips = oe.env_int("RR_PIPS_SL", 10)
    pip = oe.env_float("PIP_SIZE", 0.01)
    tick = oe.env_float("TICK_SIZE", 0.01)
    mx = oe.env_int("OCO_LAG_MAX_SEC", 5)
    step = oe.env_float("OCO_RETRY_STEP", tick)

    acct = _acct()
    if not acct:
        print("oco_manager: ERROR no account_key found")
        return {"status": "error", "reason": "no_account_key"}

    extp = f"OCO-AVG-{instrument_id}-LIM"
    exts = f"OCO-AVG-{instrument_id}-STP"

    net, avg = repo.get_net(instrument_id)
    print(f"oco_manager: net={net} avg={avg} acct={acct[:8]}...")

    if net == 0:
        stale = _cancel_all_oco_orders(instrument_id, extp, exts)
        return {"status": "no_net", "stale_cancelled": stale}

    amt = abs(int(net))
    net_dir = "Buy" if net > 0 else "Sell"
    tp, sl = oe.compute_targets(net, avg, tp_pips, sl_pips, pip, tick)
    tp_side, sl_side = oe.choose_sides(net_dir)
    existing = repo.list_orders(instrument_id)

    print(f"oco_manager: amt={amt} dir={net_dir} tp={tp} sl={sl} existing_orders={len(existing)}")

    stale = _cancel_stale_orders(instrument_id, existing, amt, extp, exts)
    if stale > 0:
        time.sleep(0.5)
        existing = repo.list_orders(instrument_id)

    has_lim = any(o["type"] == "Limit" and extp in o["ext"] and o["amt"] == amt for o in existing)
    has_stp = any(o["type"] == "Stop" and exts in o["ext"] and o["amt"] == amt for o in existing)

    res = {
        "limit": None,
        "stop": None,
        "tp": tp,
        "sl": sl,
        "amt": amt,
        "dir": net_dir,
        "stale_cancelled": stale,
        "has_lim": has_lim,
        "has_stp": has_stp,
    }

    if not has_lim:
        print(f"oco_manager: placing TP Limit {tp_side} amt={amt} price={tp}")
        rc, cid, body = _place_with_429_retry(bc.place_limit, acct, instrument_id, asset_type, tp_side, amt, tp, extp)
        if int(rc) in (200, 201):
            res["limit"] = {"rc": rc, "body": body}
            print(f"oco_manager: TP Limit placed OK rc={rc}")
        else:
            cur = oe.round_tick(tp, tick)
            tries = 0
            while True:
                rc, cid, body = _place_with_429_retry(bc.place_limit, acct, instrument_id, asset_type, tp_side, amt, cur, extp)
                if int(rc) in (200, 201):
                    res["limit"] = {"rc": rc, "body": body}
                    print(f"oco_manager: TP Limit placed OK at {cur} rc={rc}")
                    break
                code = ((body or {}).get("ErrorInfo") or {}).get("ErrorCode")
                if code != "OnWrongSideOfMarket":
                    res["limit"] = {"rc": rc, "body": body}
                    print(f"oco_manager: TP Limit failed permanently rc={rc} code={code}")
                    break
                tries += 1
                if tries >= mx:
                    res["limit"] = {"rc": rc, "body": body}
                    print(f"oco_manager: TP Limit failed after {tries} retries")
                    break
                cur = oe.round_tick(cur + step if net_dir == "Buy" else cur - step, tick)
                time.sleep(0.3)

    time.sleep(1.0)

    if not has_stp:
        print(f"oco_manager: placing SL Stop {sl_side} amt={amt} price={sl}")
        rc, cid, body = _place_with_429_retry(bc.place_stop, acct, instrument_id, asset_type, sl_side, amt, sl, exts)
        if int(rc) in (200, 201):
            res["stop"] = {"rc": rc, "body": body}
            print(f"oco_manager: SL Stop placed OK rc={rc}")
        else:
            cur = oe.round_tick(sl, tick)
            tries = 0
            while True:
                rc, cid, body = _place_with_429_retry(bc.place_stop, acct, instrument_id, asset_type, sl_side, amt, cur, exts)
                if int(rc) in (200, 201):
                    res["stop"] = {"rc": rc, "body": body}
                    print(f"oco_manager: SL Stop placed OK at {cur} rc={rc}")
                    break
                code = ((body or {}).get("ErrorInfo") or {}).get("ErrorCode")
                if code != "OnWrongSideOfMarket":
                    res["stop"] = {"rc": rc, "body": body}
                    print(f"oco_manager: SL Stop failed permanently rc={rc} code={code}")
                    break
                tries += 1
                if tries >= mx:
                    res["stop"] = {"rc": rc, "body": body}
                    print(f"oco_manager: SL Stop failed after {tries} retries")
                    break
                cur = oe.round_tick(cur - step if net_dir == "Buy" else cur + step, tick)
                time.sleep(0.3)

    return res


class OcoManager:
    def __init__(self, acct_key=None, instrument_id=None, asset_type=None):
        self.acct_key = acct_key
        self.instrument_id = instrument_id
        self.asset_type = asset_type

    def ensure(self):
        if self.acct_key:
            os.environ["ACCOUNT_KEY"] = str(self.acct_key)
        return ensure(self.instrument_id, self.asset_type)
