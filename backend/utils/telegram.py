"""Avisos por Telegram con el bot de Datil (token en la variable de entorno TELEGRAM_DATIL).

Cada usuario enlaza su Telegram una vez: abre el bot con un enlace que lleva su codigo (t.me/<bot>?start=<codigo>),
toca Iniciar y luego confirma en la plataforma; ahi se busca su mensaje y se guarda su chat. Desde entonces todo
aviso que entra a su bandeja (notifications.add) le llega tambien por Telegram.
No hay proceso en segundo plano ni webhook: el mensaje del usuario se lee con getUpdates cuando el confirma.
"""
import hashlib
import hmac
import logging
import threading

import requests

from config import Config

log = logging.getLogger(__name__)

_bot_username = None


def enabled() -> bool:
    return bool(Config.TELEGRAM_TOKEN)


def _call(method, **params):
    """Resultado de la API de Telegram, o None si falla. Nunca lanza ni deja el token en el log."""
    try:
        response = requests.post(f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/{method}", json=params, timeout=10)
        body = response.json()
    except (requests.RequestException, ValueError) as e:
        log.error("Telegram %s fallo: %s", method, type(e).__name__)
        return None
    if not body.get("ok"):
        log.error("Telegram %s rechazado: %s", method, body.get("description"))
        return None
    return body["result"]


def link_code(username: str) -> str:
    """Codigo fijo por usuario y no adivinable (sale de SECRET_KEY): no hay que guardarlo."""
    return hmac.new(Config.SECRET_KEY.encode(), f"telegram:{username}".encode(), hashlib.sha256).hexdigest()[:16]


def link_url(username: str):
    """Enlace que abre el bot con el codigo del usuario; None si el bot no responde."""
    global _bot_username
    if _bot_username is None:
        me = _call("getMe")
        if me is None:
            return None
        _bot_username = me["username"]
    return f"https://t.me/{_bot_username}?start={link_code(username)}"


def find_chat(username: str):
    """Chat de Telegram desde el que se mando el codigo del usuario (el mas reciente), o None."""
    updates = _call("getUpdates", limit=100, allowed_updates=["message"]) or []
    wanted = f"/start {link_code(username)}"
    chat_id = None
    for update in updates:
        message = update.get("message") or {}
        if (message.get("text") or "").strip() == wanted:
            chat_id = message["chat"]["id"]
    # shortcut: se leen 100 mensajes pendientes por vez; si se llena, se descartan los ya revisados
    # para ver los nuevos. Con muchos enlaces simultaneos conviene pasar a un webhook.
    if len(updates) == 100:
        _call("getUpdates", offset=updates[-1]["update_id"] + 1, limit=1)
    return chat_id


def send(chat_id, text: str):
    """Manda el mensaje sin detener la peticion: Telegram a veces tarda varios segundos."""
    if enabled() and chat_id:
        threading.Thread(target=_call, args=("sendMessage",), kwargs={"chat_id": chat_id, "text": text}, daemon=True).start()
