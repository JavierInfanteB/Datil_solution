"""Bitacora de lo que el admin opera en nombre de un cliente (audit.json: lista, del mas viejo al mas nuevo)."""
from datetime import datetime, timezone

from flask import g, request

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
