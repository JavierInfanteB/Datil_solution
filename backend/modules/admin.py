"""Panel del admin sobre los clientes: todos los clientes, sus carteras y la bitacora de lo que se opero por ellos.

Comprar y vender por un cliente usa las mismas rutas de /api/trading con `client` (ver acting_username).
"""
from datetime import date

from flask import Blueprint, jsonify, request

from modules.insights import build_insights, pnl_row
from modules.portfolio import build_portfolio_view
from utils import alerts, audit, notifications, records
from utils.accounts import load_users
from db import portfolio as pf_repo
from utils.decorators import require_auth, require_permission, require_role

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")
AUDIT_LIMIT = 50
MAX_DAYS = 365


def _clients():
    """Todos los clientes, o los que pidan los filtros `consultant` y `client` de la pantalla."""
    only, boss = request.args.get("client"), request.args.get("consultant")
    return [u for u in load_users() if u["role"] == "usuario" and (not only or u["username"] == only)
            and (not boss or u.get("consultant") == boss)]


@admin_bp.route("/clients", methods=["GET"])
@require_auth
@require_role("admin")
def list_clients():
    names = {u["username"]: u["name"] for u in load_users()}
    rows = []
    for c in _clients():
        view = build_portfolio_view(c["username"], settle=False)
        rows.append({"username": c["username"], "name": c["name"], "disabled": bool(c.get("disabled")),
                     "consultant": names.get(c.get("consultant")), "consultant_username": c.get("consultant"), "total": view["portfolio_total"],
                     "cash": view["cash"], "holdings_count": view["holdings_count"],
                     "gain_mxn": round(sum(h["gain_mxn"] for h in view["holdings"] if h.get("gain_mxn") is not None), 2)})
    return jsonify({"clients": sorted(rows, key=lambda r: -r["total"]), "audit": audit.recent(AUDIT_LIMIT)})


@admin_bp.route("/insights", methods=["GET"])
@require_auth
@require_role("admin")
def insights():
    days = min(max(request.args.get("days", 30, type=int), 1), MAX_DAYS)
    return jsonify(build_insights(_clients(), days))


WEEKS = 12  # ventana de la constancia del consultor


def _consultant_events(username):
    """Fechas de lo que hizo el consultor por sus clientes: avisos, alertas y notas personales."""
    return notifications.sent_dates(username) + alerts.created_dates(username) + records.note_dates(username)


def _kpis(consultant, rows, all_alerts):
    today = date.today()
    events = _consultant_events(consultant["username"])
    weeks = {date.fromisoformat(d[:10]).isocalendar()[:2] for d in events
             if (today - date.fromisoformat(d[:10])).days < WEEKS * 7}
    cost = sum(r["cost"] for r in rows)
    clients = {r["username"] for r in rows}
    return {
        "username": consultant["username"], "name": consultant["name"], "clients": len(rows),
        "portfolio": round(sum(r["portfolio"] for r in rows), 2),
        "unrealized": round(sum(r["unrealized"] for r in rows), 2),
        "realized": round(sum(r["realized"] for r in rows), 2),
        "total": round(sum(r["total"] for r in rows), 2),
        "return_pct": round(sum(r["unrealized"] for r in rows) / cost * 100, 2) if cost else None,
        "in_profit": sum(r["total"] > 0 for r in rows),
        "alerts_open": sum(a["level"] >= 2 for u in clients for a in all_alerts.get(u, [])),
        "actions_30d": sum((today - date.fromisoformat(d[:10])).days < 30 for d in events),
        "consistency": round(len(weeks) / WEEKS * 100),  # % de las ultimas 12 semanas con alguna accion
        "last_action": max((d[:10] for d in events), default=None),
        "clients_detail": sorted(rows, key=lambda r: -r["total"]),
    }


@admin_bp.route("/consultants", methods=["GET"])
@require_auth
@require_role("admin")
def consultants():
    """Resultados y constancia de cada consultor, con el desglose por cliente para elegirlo en pantalla."""
    transactions, all_alerts = pf_repo.transactions_by_user(), alerts.load()
    clients = _clients()
    rows = {c["username"]: pnl_row(c, build_portfolio_view(c["username"], settle=False), transactions.get(c["username"], []))
            for c in clients}
    groups = [(c, [rows[u["username"]] for u in clients if u.get("consultant") == c["username"]])
              for c in load_users() if c["role"] == "consultor"]
    orphans = [rows[u["username"]] for u in clients if not any(u.get("consultant") == c["username"] for c, _ in groups)]
    if orphans:
        groups.append(({"username": "", "name": "Sin consultor"}, orphans))
    result = [_kpis(c, r, all_alerts) for c, r in groups]
    return jsonify({"consultants": sorted(result, key=lambda k: -k["total"]),
                    "totals": {k: round(sum(c[k] for c in result), 2) for k in ("portfolio", "unrealized", "realized", "total")}})
