"""Avisos del consultor a sus clientes (notifications.json: {usuario: [aviso, ...]}, del mas viejo al mas nuevo)."""
import uuid
from datetime import datetime, timezone

from utils.data_store import read_json, write_json

FILE = "notifications.json"
KINDS = ("aviso", "riesgo", "accion")  # aviso general, alerta de riesgo, accion sugerida
ALERT = "alerta"  # lo genera el sistema cuando se cumple una alerta del cliente; el consultor no lo manda


def load():
    try:
        return read_json(FILE)
    except FileNotFoundError:
        return {}


def add(recipient, sender, kind, title, message):
    """Guarda un aviso de `sender` (dict con username y name) para el usuario `recipient`."""
    data = load()
    item = {
        "id": str(uuid.uuid4()),
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "from": sender["username"],
        "from_name": sender["name"],
        "kind": kind,
        "title": title,
        "message": message,
        "read": False,
    }
    data.setdefault(recipient, []).append(item)
    write_json(FILE, data)
    return item


def mark_read(recipient, notification_id):
    """Marca como leido un aviso del usuario; None si no existe."""
    data = load()
    item = next((n for n in data.get(recipient, []) if n["id"] == notification_id), None)
    if item is not None:
        item["read"] = True
        write_json(FILE, data)
    return item
