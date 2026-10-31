"""Panel del admin sobre los clientes: todos los clientes, sus carteras y la bitacora de lo que se opero por ellos.

Comprar y vender por un cliente usa las mismas rutas de /api/trading con `client` (ver acting_username).
"""
from flask import Blueprint, jsonify, request

from modules.insights import build_insights
from modules.portfolio import build_portfolio_view
from utils import audit
from utils.accounts import load_users
from utils.decorators import require_auth, require_permission, require_role

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")
AUDIT_LIMIT = 50
MAX_DAYS = 365


def _clients():
    return [u for u in load_users() if u["role"] == "usuario"]


@admin_bp.route("/clients", methods=["GET"])
@require_auth
@require_role("admin")
def list_clients():
    names = {u["username"]: u["name"] for u in load_users()}
    rows = []
    for c in _clients():
        view = build_portfolio_view(c["username"], settle=False)
        rows.append({"username": c["username"], "name": c["name"], "disabled": bool(c.get("disabled")),
                     "consultant": names.get(c.get("consultant")), "total": view["portfolio_total"],
                     "cash": view["cash"], "holdings_count": view["holdings_count"],
                     "gain_mxn": round(sum(h["gain_mxn"] for h in view["holdings"] if h.get("gain_mxn") is not None), 2)})
    return jsonify({"clients": sorted(rows, key=lambda r: -r["total"]), "audit": audit.load()[-AUDIT_LIMIT:][::-1]})


@admin_bp.route("/insights", methods=["GET"])
@require_auth
@require_role("admin")
def insights():
    days = min(max(request.args.get("days", 30, type=int), 1), MAX_DAYS)
    return jsonify(build_insights(_clients(), days))
