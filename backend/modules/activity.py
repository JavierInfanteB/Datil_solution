"""Registro de operaciones y avisos, filtrado por quien lo mira.

Cada compra o venta dice quien la hizo y por donde (la app del cliente, el admin en nombre del cliente, una orden
programada). El admin ve todo; el consultor, lo de sus clientes y lo que el mismo mando; el cliente, lo de su cartera.
"""
from flask import Blueprint, g, jsonify, request

from utils.accounts import clients_of, load_users
from db import portfolio as pf_repo
from utils.decorators import require_auth
from utils import notifications

activity_bp = Blueprint("activity", __name__, url_prefix="/api/activity")

LIMIT = 200
SIDE = {"buy": "Compra", "sell": "Venta"}


def _operations(users):
    name = lambda username: users.get(username, {}).get("name", username)
    rows = []
    for username, items in pf_repo.transactions_by_user().items():
        if users.get(username, {}).get("role") != "usuario":
            continue
        for t in items:
            if t["side"] not in SIDE:
                continue
            by = t.get("by", username)  # lo anterior a este registro lo hizo el propio cliente
            rows.append({"kind": "operacion", "date": t["date"], "role": t.get("by_role", "usuario"), "actor": name(by),
                         "origin": t.get("origin", "cliente"), "client": username,
                         "text": f"{SIDE[t['side']]} de {t['quantity']} × {t['symbol']}", "amount": t["total_mxn"]})
    return rows


def _notices(users):
    return [{"kind": "aviso", "date": n["date"], "role": "consultor", "actor": n["from_name"], "actor_username": n["from"],
             "client": client, "text": f"{n['title']}", "detail": n["message"], "read": n["read"], "amount": None}
            for client, items in notifications.load().items() for n in items
            if users.get(n["from"], {}).get("role") == "consultor"]


@activity_bp.route("", methods=["GET"])
@require_auth
def activity():
    me = g.current_user
    users = {u["username"]: u for u in load_users()}
    rows = _notices(users) if request.args.get("kind") == "avisos" else _operations(users)
    mine = {c["username"] for c in clients_of(me["username"])} if me["role"] == "consultor" else set()
    allowed = {
        "admin": lambda e: True,
        "consultor": lambda e: e["client"] in mine and (e["kind"] == "operacion" or e["actor_username"] == me["username"]),
        "usuario": lambda e: e["kind"] == "operacion" and e["client"] == me["username"],
    }[me["role"]]
    shown = sorted((e for e in rows if allowed(e)), key=lambda e: e["date"], reverse=True)[:LIMIT]
    return jsonify([{**e, "client_username": e["client"], "client": users.get(e["client"], {}).get("name", e["client"]),
                     "consultant": users.get(e["client"], {}).get("consultant")} for e in shown])
