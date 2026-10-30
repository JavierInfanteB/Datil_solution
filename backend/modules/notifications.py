"""Bandeja de avisos del usuario: lo que su consultor le manda (riesgos, acciones sugeridas, avisos)."""
from flask import Blueprint, g, jsonify

from utils import notifications
from utils.decorators import require_auth, require_permission, require_role

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def my_notifications():
    items = list(reversed(notifications.load().get(g.current_user["username"], [])))
    return jsonify({"unread": sum(not n["read"] for n in items), "items": items})


@notifications_bp.route("/<notification_id>/read", methods=["POST"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def read_notification(notification_id):
    item = notifications.mark_read(g.current_user["username"], notification_id)
    if item is None:
        return jsonify({"error": "El aviso no existe"}), 404
    return jsonify(item)
