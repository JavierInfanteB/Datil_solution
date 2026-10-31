"""Plan del cliente: sus metas, notas para su consultor, alertas de ganancia/perdida y reporte por periodo.

Es personal del usuario; el consultor lee lo mismo de sus clientes desde modules/consultant.py. Las carteras se
consultan sin cobrar cupones ni ejecutar ordenes (settle=False).
"""
from datetime import date

from flask import Blueprint, g, jsonify, request

from modules.portfolio import build_portfolio_view
from modules.risk import portfolio_risk_for
from utils import advice, alerts, records, report
from utils.data_store import read_json
from utils.decorators import require_auth, require_permission, require_role

plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")

MAX_TITLE = 80
MAX_NOTE = 1000
GOALS, NOTES = "goals.json", "notes.json"


def _mine(f):
    return require_auth(require_role("usuario")(require_permission("plan")(f)))


def parse_goal(body):
    """(meta, error) a partir del cuerpo de la peticion."""
    title = (body.get("title") or "").strip()
    target = body.get("target_mxn")
    if not 1 <= len(title) <= MAX_TITLE or isinstance(target, bool) or not isinstance(target, (int, float)) or target <= 0:
        return None, f"La meta necesita un título (hasta {MAX_TITLE}) y un monto mayor que 0"
    goal = {"title": title, "target_mxn": target}
    if body.get("target_date"):
        try:
            goal["target_date"] = date.fromisoformat(body["target_date"]).isoformat()
        except (TypeError, ValueError):
            return None, "La fecha debe ser AAAA-MM-DD"
    return goal, None


def parse_note(body):
    text = (body.get("text") or "").strip()
    if not 1 <= len(text) <= MAX_NOTE:
        return None, f"La nota va de 1 a {MAX_NOTE} caracteres"
    return {"text": text}, None


def period_report(username, period):
    """Reporte del usuario por `period` (month, quarter, year); lo usan tambien el consultor y el admin."""
    view = build_portfolio_view(username, settle=False)
    try:
        suggestions = advice.suggestions(portfolio_risk_for(username, view))
    except ValueError:  # portafolio vacio
        suggestions = []
    transactions = read_json("transactions.json").get(username, [])
    return report.build(period, transactions, view, records.items(GOALS, username), suggestions, date.today())


def requested_period():
    period = request.args.get("period", "month")
    return period if period in report.PERIODS else "month"


@plan_bp.route("/goals", methods=["GET"])
@_mine
def get_goals():
    return jsonify(records.items(GOALS, g.current_user["username"]))


@plan_bp.route("/goals", methods=["POST"])
@_mine
def add_goal():
    goal, error = parse_goal(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(records.add(GOALS, g.current_user["username"], goal)), 201


@plan_bp.route("/goals/<goal_id>", methods=["DELETE"])
@_mine
def delete_goal(goal_id):
    if not records.remove(GOALS, g.current_user["username"], goal_id):
        return jsonify({"error": "La meta no existe"}), 404
    return jsonify({"id": goal_id})


@plan_bp.route("/notes", methods=["GET"])
@_mine
def get_notes():
    return jsonify(list(reversed(records.items(NOTES, g.current_user["username"]))))


@plan_bp.route("/notes", methods=["POST"])
@_mine
def add_note():
    note, error = parse_note(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(records.add(NOTES, g.current_user["username"], note)), 201


@plan_bp.route("/notes/<note_id>", methods=["DELETE"])
@_mine
def delete_note(note_id):
    if not records.remove(NOTES, g.current_user["username"], note_id):
        return jsonify({"error": "La nota no existe"}), 404
    return jsonify({"id": note_id})


@plan_bp.route("/alerts", methods=["GET"])
@_mine
def get_alerts():
    username = g.current_user["username"]
    return jsonify(alerts.evaluate(username, build_portfolio_view(username, settle=False)))


@plan_bp.route("/alerts", methods=["POST"])
@_mine
def add_alert():
    body = request.get_json(silent=True) or {}
    alert, error = alerts.create(g.current_user["username"], g.current_user, body.get("symbol"), body.get("kind"),
                                 body.get("percent"), body.get("indication") or "aviso")
    if error:
        return jsonify({"error": error}), 400
    return jsonify(alert), 201


@plan_bp.route("/alerts/<alert_id>", methods=["DELETE"])
@_mine
def delete_alert(alert_id):
    if not alerts.remove(g.current_user["username"], alert_id, g.current_user):
        return jsonify({"error": "La alerta no existe o no es tuya"}), 404
    return jsonify({"id": alert_id})


@plan_bp.route("/report", methods=["GET"])
@_mine
def get_report():
    return jsonify(period_report(g.current_user["username"], requested_period()))
