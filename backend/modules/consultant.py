"""Panel del consultor: los clientes que tiene asignados, su actividad, su riesgo, que decisiones tomar
y los avisos que les manda.

Es un panel personal: solo el consultor lo usa y solo ve a sus clientes (el admin los asigna desde
Usuarios y permisos). Las carteras se consultan sin cobrar cupones ni ejecutar ordenes pendientes
(ver build_portfolio_view); lo unico que el consultor escribe son avisos.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request

from modules.insights import build_insights
from modules.portfolio import build_portfolio_view
from modules.risk import BENCHMARK, assess, load_stock, portfolio_risk_for
from modules.plan import parse_note, period_report, requested_period, GOALS, NOTES
from utils import advice, alerts, ideas, notifications, records, trade_timing
from utils.accounts import clients_of
from utils.data_store import read_json
from utils.decorators import require_auth, require_permission, require_role

consultant_bp = Blueprint("consultant", __name__, url_prefix="/api/consultant")

TOP = 5
MAX_SUGGESTIONS = 200
MAX_DAYS = 365
MAX_TITLE = 80
MAX_MESSAGE = 1000
TIMELINE_LIMIT = 100
TRADE_FIELDS = ("id", "date", "type", "side", "symbol", "name", "quantity", "price", "currency",
                "total_mxn", "realized_pnl_mxn")


def _clients():
    return clients_of(g.current_user["username"])


def _client(username):
    return next((c for c in _clients() if c["username"] == username), None)


@consultant_bp.route("/dashboard", methods=["GET"])
@require_auth
@require_role("consultor")
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


@consultant_bp.route("/insights", methods=["GET"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def insights():
    days = min(max(request.args.get("days", 30, type=int), 1), MAX_DAYS)
    return jsonify(build_insights(_clients(), days))


@consultant_bp.route("/clients/<username>", methods=["GET"])
@require_auth
@require_role("consultor")
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
@require_role("consultor")
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


@consultant_bp.route("/clients/<username>/notifications", methods=["GET"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def sent_notifications(username):
    """Los avisos que este consultor le ha mandado al cliente, del mas nuevo al mas viejo, y si ya los leyo."""
    if _client(username) is None:
        return jsonify({"error": "Cliente no encontrado"}), 404
    sent = [n for n in notifications.load().get(username, []) if n["from"] == g.current_user["username"]]
    return jsonify(list(reversed(sent)))


@consultant_bp.route("/clients/<username>/notifications", methods=["POST"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def send_notification(username):
    if _client(username) is None:
        return jsonify({"error": "Cliente no encontrado"}), 404

    body = request.get_json(silent=True) or {}
    kind = body.get("kind") or "aviso"
    title = (body.get("title") or "").strip()
    message = (body.get("message") or "").strip()
    if kind not in notifications.KINDS:
        return jsonify({"error": "Tipo de aviso inválido"}), 400
    if not 1 <= len(title) <= MAX_TITLE or not 1 <= len(message) <= MAX_MESSAGE:
        return jsonify({"error": f"El título (hasta {MAX_TITLE}) y el mensaje (hasta {MAX_MESSAGE}) son requeridos"}), 400

    return jsonify(notifications.add(username, g.current_user, kind, title, message)), 201


# ---------------------------------------------------------------- plan del cliente: metas, notas, alertas y reporte

PRIVATE_NOTES = "consultant_notes.json"  # {"consultor/cliente": [nota]}: solo las ve quien las escribe


def _private_key(username):
    return f"{g.current_user['username']}/{username}"


def _client_or_404(username):
    return (None, (jsonify({"error": "Cliente no encontrado"}), 404)) if _client(username) is None else (username, None)


@consultant_bp.route("/alerts", methods=["GET"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def alerts_dashboard():
    """Las alertas de todos sus clientes con su nivel de hoy: 3 cumplida, 2 al 80% del umbral, 1 al 60%."""
    rows = []
    for client in _clients():
        view = build_portfolio_view(client["username"], settle=False)
        rows += [{**a, "username": client["username"], "client": client["name"]}
                 for a in alerts.evaluate(client["username"], view)]
    return jsonify({
        "counts": {level: sum(r["level"] == level for r in rows) for level in (3, 2, 1, 0)},
        "alerts": sorted(rows, key=lambda r: (-r["level"], r["client"])),
    })


@consultant_bp.route("/clients/<username>/plan", methods=["GET"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def client_plan(username):
    _, error = _client_or_404(username)
    if error:
        return error
    view = build_portfolio_view(username, settle=False)
    return jsonify({
        "goals": records.items(GOALS, username),
        "notes": list(reversed(records.items(NOTES, username))),
        "private_notes": list(reversed(records.items(PRIVATE_NOTES, _private_key(username)))),
        "alerts": alerts.evaluate(username, view),
        "portfolio_total": view["portfolio_total"],
    })


@consultant_bp.route("/clients/<username>/private-notes", methods=["POST"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def add_private_note(username):
    _, error = _client_or_404(username)
    if error:
        return error
    note, error = parse_note(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(records.add(PRIVATE_NOTES, _private_key(username), note)), 201


@consultant_bp.route("/clients/<username>/private-notes/<note_id>", methods=["DELETE"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def delete_private_note(username, note_id):
    if _client(username) is None or not records.remove(PRIVATE_NOTES, _private_key(username), note_id):
        return jsonify({"error": "La nota no existe"}), 404
    return jsonify({"id": note_id})


@consultant_bp.route("/clients/<username>/alerts", methods=["POST"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def add_client_alert(username):
    """Alerta puesta por el consultor: solo la ve el, el cliente no recibe aviso al cumplirse."""
    _, error = _client_or_404(username)
    if error:
        return error
    body = request.get_json(silent=True) or {}
    alert, error = alerts.create(username, g.current_user, body.get("symbol"), body.get("kind"),
                                 body.get("percent"), body.get("indication") or "aviso")
    if error:
        return jsonify({"error": error}), 400
    return jsonify(alert), 201


@consultant_bp.route("/clients/<username>/alerts/<alert_id>", methods=["DELETE"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def delete_client_alert(username, alert_id):
    if _client(username) is None or not alerts.remove(username, alert_id, g.current_user):
        return jsonify({"error": "La alerta no existe o la puso el cliente"}), 404
    return jsonify({"id": alert_id})


@consultant_bp.route("/clients/<username>/report", methods=["GET"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def client_report(username):
    _, error = _client_or_404(username)
    if error:
        return error
    return jsonify(period_report(username, requested_period()))


def _idea(symbol):
    try:
        risk = assess(symbol)
        if risk["level"] != "bajo":
            return None
        found = ideas.facts(load_stock(symbol)["series"])
    except Exception:
        return None  # sin historico de Yahoo o con historia insuficiente
    why = ideas.reasons(found)
    return {"symbol": symbol, "name": risk["name"], "risk": {"level": risk["level"], "score": risk["score"]},
            "facts": found, "reasons": why} if why else None


@consultant_bp.route("/ideas", methods=["GET"])
@require_auth
@require_role("consultor")
@require_permission("consultor")
def stock_ideas():
    """Acciones de riesgo bajo cerca de su minimo o con buena tendencia: para revisar, no una prediccion."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        found = [i for i in pool.map(_idea, ideas.WATCHLIST) if i]
    return jsonify({"ideas": sorted(found, key=lambda i: i["risk"]["score"]), "reviewed": len(ideas.WATCHLIST)})
