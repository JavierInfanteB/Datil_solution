"""Panel del consultor: los clientes que tiene asignados, su actividad, su riesgo y que decisiones tomar.

El consultor solo ve a sus clientes (el admin ve a todos los usuarios) y solo lee: las carteras se
consultan sin cobrar cupones ni ejecutar ordenes pendientes (ver build_portfolio_view).
"""
from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request

from modules.portfolio import build_portfolio_view
from modules.risk import BENCHMARK, load_stock, portfolio_risk_for
from utils import advice, trade_timing
from utils.accounts import clients_of, load_users
from utils.data_store import read_json
from utils.decorators import require_auth, require_permission, require_role

consultant_bp = Blueprint("consultant", __name__, url_prefix="/api/consultant")

TOP = 5
MAX_SUGGESTIONS = 20
MAX_DAYS = 365
TIMELINE_LIMIT = 100
TRADE_FIELDS = ("id", "date", "type", "side", "symbol", "name", "quantity", "price", "currency",
                "total_mxn", "realized_pnl_mxn")


def _clients():
    user = g.current_user
    if user["role"] == "admin":
        return [u for u in load_users() if u["role"] == "usuario"]
    return clients_of(user["username"])


def _client(username):
    return next((c for c in _clients() if c["username"] == username), None)


@consultant_bp.route("/dashboard", methods=["GET"])
@require_auth
@require_role("consultor", "admin")
@require_permission("consultor")
def dashboard():
    days = min(max(request.args.get("days", 30, type=int), 1), MAX_DAYS)
    today = date.today()
    first_day = (today - timedelta(days=days - 1)).isoformat()
    all_transactions = read_json("transactions.json")

    activity = {(today - timedelta(days=n)).isoformat(): {"buys": 0, "sells": 0} for n in range(days - 1, -1, -1)}
    rows, positions, sales, suggestions = [], [], [], []

    # shortcut: un cliente tras otro (las cotizaciones de Yahoo quedan en cache 6 h); paralelizar si pasan de ~20 clientes.
    for client in _clients():
        username, label = client["username"], {"username": client["username"], "client": client["name"]}
        view = build_portfolio_view(username, settle=False)
        try:
            risk = portfolio_risk_for(username, view)
        except ValueError:  # portafolio vacio
            risk = None
        decisions = advice.suggestions(risk) if risk else []

        trades = [t for t in all_transactions.get(username, [])
                  if t["side"] in ("buy", "sell") and t["date"][:10] >= first_day]
        for t in trades:
            day = activity.get(t["date"][:10])
            if day:
                day["buys" if t["side"] == "buy" else "sells"] += 1

        buys = sum(t["side"] == "buy" for t in trades)
        rows.append({
            **label,
            "total": view["portfolio_total"],
            "holdings_count": view["holdings_count"],
            "risk": {"level": risk["stocks"]["level"], "score": risk["stocks"]["weighted_score"]} if risk else None,
            "buys": buys,
            "sells": len(trades) - buys,
            "volume_mxn": round(sum(t["total_mxn"] for t in trades), 2),
            "alerts": sum(d["severity"] == "alta" for d in decisions),
        })
        positions += [{**label, "type": h["type"], "symbol": h["symbol"], "name": h["name"],
                       "gain_percent": h["gain_percent"], "gain_mxn": h["gain_mxn"]}
                      for h in view["holdings"] if h.get("gain_percent") is not None]
        sales += [{**label, "symbol": t["symbol"], "name": t["name"], "date": t["date"][:10],
                   "realized_pnl_mxn": t["realized_pnl_mxn"], "total_mxn": t["total_mxn"]}
                  for t in trades if t["side"] == "sell" and t.get("realized_pnl_mxn") is not None]
        suggestions += [{**label, **d} for d in decisions]

    return jsonify({
        "days": days,
        "totals": {
            "clients": len(rows),
            "portfolio_total": round(sum(r["total"] for r in rows), 2),
            "buys": sum(r["buys"] for r in rows),
            "sells": sum(r["sells"] for r in rows),
            "volume_mxn": round(sum(r["volume_mxn"] for r in rows), 2),
            "high_risk": sum(bool(r["risk"]) and r["risk"]["level"] == "alto" for r in rows),
            "alerts": sum(r["alerts"] for r in rows),
        },
        "clients": sorted(rows, key=lambda r: (-r["alerts"], r["client"])),
        "activity": [{"date": d, **counts} for d, counts in activity.items()],
        "top_positions": sorted(positions, key=lambda p: -p["gain_percent"])[:TOP],
        "top_sales": sorted(sales, key=lambda s: -s["realized_pnl_mxn"])[:TOP],
        "suggestions": sorted(suggestions, key=lambda s: advice.SEVERITY_ORDER[s["severity"]])[:MAX_SUGGESTIONS],
    })


@consultant_bp.route("/clients/<username>", methods=["GET"])
@require_auth
@require_role("consultor", "admin")
@require_permission("consultor")
def client_detail(username):
    client = _client(username)
    if client is None:
        return jsonify({"error": "Cliente no encontrado"}), 404

    view = build_portfolio_view(username, settle=False)
    try:
        risk = portfolio_risk_for(username, view)
        decisions = advice.suggestions(risk)
    except ValueError as exc:
        risk, decisions = {"error": str(exc)}, []

    return jsonify({
        "client": {"username": username, "name": client["name"]},
        "portfolio": view,
        "risk": risk,
        "decisions": decisions,
    })


def _timing(trade):
    try:
        stock, benchmark = load_stock(trade["symbol"]), load_stock(BENCHMARK)
    except Exception:
        return None  # sin historico de Yahoo para ese simbolo
    return trade_timing.analyze(stock["series_mxn"], stock["series"], benchmark["series"],
                                trade["date"][:10], trade["side"])


@consultant_bp.route("/clients/<username>/timeline", methods=["GET"])
@require_auth
@require_role("consultor", "admin")
@require_permission("consultor")
def client_timeline(username):
    if _client(username) is None:
        return jsonify({"error": "Cliente no encontrado"}), 404

    transactions = read_json("transactions.json").get(username, [])
    held = trade_timing.holding_days(transactions)
    rows = []
    for t in sorted(transactions, key=lambda t: t["date"], reverse=True)[:TIMELINE_LIMIT]:
        row = {field: t.get(field) for field in TRADE_FIELDS}
        row["holding_days"] = held.get(t["id"])
        row["timing"] = _timing(t) if t["type"] == "accion" and t["side"] in ("buy", "sell") else None
        rows.append(row)
    return jsonify(rows)
