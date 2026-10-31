"""Bitacora de lo que el admin opera en nombre de un cliente (audit.json: lista, del mas viejo al mas nuevo)."""
from datetime import datetime, timezone

from flask import g, has_request_context, request

from utils.data_store import read_json, write_json

FILE = "audit.json"


def load():
    try:
        return read_json(FILE)
    except FileNotFoundError:
        return []


def record_admin_trade(action, order):
    """Anota una compra/venta del admin; no hace nada si quien opera es el propio usuario."""
    if g.current_user["role"] != "admin":
        return
    client = request.args.get("client") or (request.get_json(silent=True) or {}).get("client")
    entry = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "admin": g.current_user["username"],
             "client": client, "action": action, "symbol": order["symbol"], "quantity": order["quantity"],
             "asset_type": order["asset_type"]}
    write_json(FILE, load() + [entry])


def tag(event):
    """Anota en una operacion quien la hizo (by, by_role) y por donde (origin): el cliente en la app, el admin en nombre
    del cliente, una orden programada o algo automatico (cupon, vencimiento). Respeta lo que la operacion ya traiga."""
    if "origin" in event:
        return event
    user = getattr(g, "current_user", None) if has_request_context() else None
    if event["side"] in ("coupon", "redeem") or user is None:
        event.update(by="sistema", by_role="sistema", origin="automático")
    else:
        event.update(by=user["username"], by_role=user["role"], origin="admin" if user["role"] == "admin" else "cliente")
    return event
