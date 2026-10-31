"""Actividad reciente, filtrada por quien la mira.

El admin ve lo de todos (clientes, consultores y administradores); el consultor, lo de sus clientes y lo que el
mismo hizo; el cliente, solo lo de los clientes, o sea sus propias operaciones.
"""
from flask import Blueprint, g, jsonify

from utils import audit, notifications
from utils.accounts import clients_of, load_users
from utils.data_store import read_json
from utils.decorators import require_auth

activity_bp = Blueprint("activity", __name__, url_prefix="/api/activity")

LIMIT = 100
SIDE = {"buy": "Compra", "sell": "Venta"}


def _events():
    users = {u["username"]: u for u in load_users()}
    name = lambda username: users.get(username, {}).get("name", username)
    rows = []
    for username, items in read_json("transactions.json").items():
        if users.get(username, {}).get("role") != "usuario":
            continue
        rows += [{"date": t["date"], "role": "usuario", "actor": name(username), "client": username,
                  "text": f"{SIDE[t['side']]} de {t['quantity']} × {t['symbol']}", "amount": t["total_mxn"]}
                 for t in items if t["side"] in SIDE]
    rows += [{"date": a["date"], "role": "admin", "actor": name(a["admin"]), "client": a["client"],
              "text": f"{SIDE.get(a['action'], a['action'])} de {a['quantity']} × {a['symbol']} en nombre del cliente", "amount": None}
             for a in audit.load()]
    for client, items in notifications.load().items():
        rows += [{"date": n["date"], "role": "consultor", "actor": n["from_name"], "actor_username": n["from"], "client": client,
                  "text": f"Aviso «{n['title']}»", "amount": None}
                 for n in items if users.get(n["from"], {}).get("role") == "consultor"]
    return rows


@activity_bp.route("", methods=["GET"])
@require_auth
def activity():
    me = g.current_user
    mine = {c["username"] for c in clients_of(me["username"])} if me["role"] == "consultor" else set()
    allowed = {
        "admin": lambda e: True,
        "consultor": lambda e: (e["role"] == "usuario" and e["client"] in mine)
        or (e["role"] == "consultor" and e["actor_username"] == me["username"]),
        "usuario": lambda e: e["role"] == "usuario" and e["client"] == me["username"],
    }[me["role"]]
    names = {u["username"]: u["name"] for u in load_users()}
    rows = sorted((e for e in _events() if allowed(e)), key=lambda e: e["date"], reverse=True)[:LIMIT]
    return jsonify([{**e, "client": names.get(e["client"], e["client"])} for e in rows])
