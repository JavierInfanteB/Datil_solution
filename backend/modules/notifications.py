"""Bandeja de avisos del usuario: lo que su consultor le manda (riesgos, acciones sugeridas, avisos)."""
from flask import Blueprint, g, jsonify

from db import connection as c
from utils import cifrado, notifications, telegram
from utils.decorators import require_auth, require_permission, require_role

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def my_notifications():
    items = list(reversed(notifications.load(g.current_user["username"])[g.current_user["username"]]))
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


def _available():
    """Hay bot y hay clave para guardar el chat cifrado (nunca se guarda en claro)."""
    return telegram.enabled() and cifrado.disponible()


def _set_chat(username, chat_id):
    """Guarda cifrado (o borra, con None) el chat de Telegram del usuario."""
    user = c.fetch_one("SELECT id FROM usuarios WHERE usuario = %s", (username,))
    value = None if chat_id is None else cifrado.cifrar(str(chat_id), notifications.telegram_context(user["id"]))
    c.execute("UPDATE usuarios SET telegram_chat_cifrado = %s WHERE id = %s", (value, user["id"]))


@notifications_bp.route("/telegram", methods=["GET"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def telegram_status():
    """Si hay bot, si el usuario ya enlazo su Telegram y el enlace para hacerlo."""
    username = g.current_user["username"]
    linked = notifications.telegram_chat(username) is not None
    url = telegram.link_url(username) if _available() and not linked else None
    return jsonify({"available": _available(), "linked": linked, "url": url})


@notifications_bp.route("/telegram", methods=["POST"])
@require_auth
@require_role("usuario")
@require_permission("avisos")
def telegram_link():
    """El usuario ya toco Iniciar en el bot: se busca su mensaje y se guarda su chat."""
    if not _available():
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
    return jsonify({"available": _available(), "linked": False, "url": telegram.link_url(g.current_user["username"]) if _available() else None})
