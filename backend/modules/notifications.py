"""Bandeja de avisos del usuario: lo que su consultor le manda (riesgos, acciones sugeridas, avisos)."""
from flask import Blueprint, g, jsonify

from utils import notifications, telegram
from utils.data_store import read_json, write_json
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


def _set_chat(username, chat_id):
    """Guarda (o borra, con None) el chat de Telegram del usuario."""
    data = read_json("users.json")
    user = next(u for u in data["users"] if u["username"] == username)
    if chat_id is None:
        user.pop("telegram_chat_id", None)
    else:
        user["telegram_chat_id"] = chat_id
    write_json("users.json", data)


@notifications_bp.route("/telegram", methods=["GET"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def telegram_status():
    """Si hay bot, si el usuario ya enlazo su Telegram y el enlace para hacerlo."""
    user = next(u for u in read_json("users.json")["users"] if u["username"] == g.current_user["username"])
    linked = bool(user.get("telegram_chat_id"))
    url = telegram.link_url(user["username"]) if telegram.enabled() and not linked else None
    return jsonify({"available": telegram.enabled(), "linked": linked, "url": url})


@notifications_bp.route("/telegram", methods=["POST"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def telegram_link():
    """El usuario ya toco Iniciar en el bot: se busca su mensaje y se guarda su chat."""
    if not telegram.enabled():
        return jsonify({"error": "Los avisos por Telegram no estan disponibles"}), 503
    chat_id = telegram.find_chat(g.current_user["username"])
    if chat_id is None:
        return jsonify({"error": "Aún no llega tu mensaje. Abre el bot con el enlace, toca Iniciar y vuelve a confirmar."}), 404
    _set_chat(g.current_user["username"], chat_id)
    telegram.send(chat_id, "Listo: desde ahora los avisos de Datil Solutions te llegan también por aquí.")
    return jsonify({"available": True, "linked": True, "url": None})


@notifications_bp.route("/telegram", methods=["DELETE"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def telegram_unlink():
    _set_chat(g.current_user["username"], None)
    return jsonify({"available": telegram.enabled(), "linked": False, "url": telegram.link_url(g.current_user["username"])})
