"""Alertas de ganancia o perdida sobre una posicion (o todo el portafolio, simbolo "*").

La crea el cliente (al comprar o despues) o su consultor. Al cliente se le avisa cuando se cumple; el consultor
las ve en su panel desde antes: ya al 60% y al 80% del umbral (con 10% de perdida, a las perdidas de 6% y 8%) para
que pueda actuar. La indicacion (avisar, vender, comprar) es solo una sugerencia: nunca se opera sola.
Las alertas se evaluan cuando alguien abre la app, no hay un proceso en segundo plano.
"""
import uuid
from datetime import datetime, timezone

from utils import notifications
from utils.data_store import read_json, write_json

FILE = "alerts.json"  # {usuario: [alerta, ...]}
KINDS = ("loss", "gain")
INDICATIONS = ("aviso", "vender", "comprar")
NEAR = (0.6, 0.8)  # fracciones del umbral que marcan los niveles 1 (atencion) y 2 (cerca); el 3 es cumplida
SYSTEM = {"username": "sistema", "name": "Datil Solution"}
INDICATION_TEXT = {"aviso": "Solo es un aviso.", "vender": "Indicación: considera vender.", "comprar": "Indicación: considera comprar más."}


def load():
    return read_json(FILE, {})


def move_percent(view, symbol):
    """Ganancia (+) o perdida (-) en % sobre el costo de la posicion; None si no hay posicion valuada."""
    rows = [h for h in view["holdings"] if h.get("gain_mxn") is not None and symbol in ("*", h["symbol"])]
    cost = sum(h["value"] - h["gain_mxn"] for h in rows)
    return round(sum(h["gain_mxn"] for h in rows) / cost * 100, 2) if rows and cost > 0 else None


def level_of(alert, move):
    """0 lejos, 1 atencion, 2 cerca, 3 cumplida."""
    if move is None:
        return 0
    ratio = (-move if alert["kind"] == "loss" else move) / alert["percent"]
    return 3 if ratio >= 1 else 2 if ratio >= NEAR[1] else 1 if ratio >= NEAR[0] else 0


def create(username, author, symbol, kind, percent, indication="aviso"):
    """Guarda una alerta de `username` hecha por `author` (dict con username y role). Devuelve (alerta, error)."""
    symbol = str(symbol or "").strip().upper()
    if not symbol or len(symbol) > 20:
        return None, "Falta el símbolo de la acción o bono"
    if kind not in KINDS or indication not in INDICATIONS:
        return None, "Tipo o indicación inválidos"
    top = 100 if kind == "loss" else 1000
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not 0 < percent <= top:
        return None, f"El porcentaje debe ser mayor que 0 y de {top} como máximo"
    alert = {"id": str(uuid.uuid4()), "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "symbol": symbol,
             "kind": kind, "percent": percent, "indication": indication, "by": author["username"],
             "by_role": author["role"], "level": 0}
    data = load()
    data.setdefault(username, []).append(alert)
    write_json(FILE, data)
    return alert, None


def remove(username, alert_id, author):
    """Cada quien borra las que puso: el cliente las suyas y el consultor las de el."""
    data = load()
    kept = [a for a in data.get(username, []) if not (a["id"] == alert_id and a["by"] == author["username"])]
    if len(kept) == len(data.get(username, [])):
        return False
    data[username] = kept
    write_json(FILE, data)
    return True


def evaluate(username, view):
    """Alertas del usuario con su movimiento y nivel de hoy. Al cumplirse una del cliente, le deja un aviso."""
    data = load()
    rows, changed = [], False
    for alert in data.get(username, []):
        move = move_percent(view, alert["symbol"])
        level = level_of(alert, move)
        if level != alert["level"]:
            if level == 3 and alert["by_role"] == "usuario":
                word = "perdió" if alert["kind"] == "loss" else "ganó"
                notifications.add(username, SYSTEM, notifications.ALERT, f"Alerta cumplida: {alert['symbol']}",
                                  f"{alert['symbol']} {word} {abs(move)}% desde tu costo (tu alerta era de {alert['percent']}%). "
                                  f"{INDICATION_TEXT[alert['indication']]}")
            alert["level"], alert["level_at"], changed = level, datetime.now(timezone.utc).isoformat(timespec="seconds"), True
        rows.append({**alert, "move": move})
    if changed:
        write_json(FILE, data)
    return rows
