"""Alertas de ganancia o perdida sobre una posicion (o todo el portafolio, simbolo "*").

La crea el cliente (al comprar o despues) o su consultor. Al cliente se le avisa cuando se cumple; el consultor
las ve en su panel desde antes: ya al 60% y al 80% del umbral (con 10% de perdida, a las perdidas de 6% y 8%) para
que pueda actuar. La indicacion (avisar, vender, comprar) es solo una sugerencia: nunca se opera sola.
Las alertas se evaluan cuando alguien abre la app, no hay un proceso en segundo plano.
Persisten en alertas (regla y nivel actual) y eventos_alerta (cada cambio de nivel).
"""
from db import connection as c
from db.connection import as_float, as_num, iso, transaction
from utils import notifications

KINDS = ("loss", "gain")
KIND_TO_DB = {"loss": "perdida", "gain": "ganancia"}
KIND_FROM_DB = {v: k for k, v in KIND_TO_DB.items()}
INDICATIONS = ("aviso", "vender", "comprar")
NEAR = (0.6, 0.8)  # fracciones del umbral que marcan los niveles 1 (atencion) y 2 (cerca); el 3 es cumplida
SYSTEM = {"username": "sistema", "name": "Datil Solution"}
INDICATION_TEXT = {"aviso": "Solo es un aviso.", "vender": "Indicación: considera vender.", "comprar": "Indicación: considera comprar más."}

SQL = ("SELECT a.id, a.uid, a.creada_en, a.simbolo, a.tipo, a.porcentaje, a.indicacion, a.nivel, a.nivel_desde, a.rol_creador, "
       "cl.usuario AS cliente, au.usuario AS autor FROM alertas a JOIN usuarios cl ON cl.id = a.cliente_id "
       "JOIN usuarios au ON au.id = a.creada_por WHERE a.activa")


def _item(r):
    item = {"id": str(r["uid"]), "date": iso(r["creada_en"]), "symbol": r["simbolo"], "kind": KIND_FROM_DB[r["tipo"]],
            "percent": as_num(r["porcentaje"]), "indication": r["indicacion"], "by": r["autor"], "by_role": r["rol_creador"],
            "level": r["nivel"]}
    if r["nivel_desde"]:
        item["level_at"] = iso(r["nivel_desde"])
    return item


def load():
    """{usuario: [alerta, ...]} de todos los clientes."""
    data = {}
    for r in c.fetch_all(SQL + " ORDER BY a.creada_en, a.id"):
        data.setdefault(r["cliente"], []).append(_item(r))
    return data


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
    if round(percent, 2) <= 0:
        return None, "El porcentaje debe ser mayor que 0"
    row = c.fetch_one(
        "INSERT INTO alertas (cliente_id, creada_por, rol_creador, simbolo, tipo, porcentaje, indicacion) "
        "VALUES ((SELECT id FROM usuarios WHERE usuario = %s), (SELECT id FROM usuarios WHERE usuario = %s), %s, %s, %s, %s, %s) "
        "RETURNING id", (username, author["username"], author["role"], symbol, KIND_TO_DB[kind], percent, indication))
    return _item(c.fetch_one(SQL + " AND a.id = %s", (row["id"],))), None


def remove(username, alert_id, author):
    """Cada quien borra las que puso: el cliente las suyas y el consultor las de el."""
    return c.execute(
        "DELETE FROM alertas WHERE uid::text = %s AND cliente_id = (SELECT id FROM usuarios WHERE usuario = %s) "
        "AND creada_por = (SELECT id FROM usuarios WHERE usuario = %s)", (alert_id, username, author["username"])) > 0


def evaluate(username, view):
    """Alertas del usuario con su movimiento y nivel de hoy. Al cumplirse una del cliente, le deja un aviso."""
    rows = []
    with transaction():
        mine = c.fetch_all(SQL + " AND cl.usuario = %s ORDER BY a.creada_en, a.id FOR UPDATE OF a", (username,))
        for r in mine:
            alert = _item(r)
            move = move_percent(view, alert["symbol"])
            level = level_of(alert, move)
            if level != alert["level"]:
                event = c.fetch_one("INSERT INTO eventos_alerta (alerta_id, nivel_anterior, nivel_nuevo, movimiento_pct) "
                                    "VALUES (%s, %s, %s, %s) RETURNING id", (r["id"], alert["level"], level, move))
                if level == 3 and alert["by_role"] == "usuario":
                    word = "perdió" if alert["kind"] == "loss" else "ganó"
                    notifications.add(username, SYSTEM, notifications.ALERT, f"Alerta cumplida: {alert['symbol']}",
                                      f"{alert['symbol']} {word} {abs(move)}% desde tu costo (tu alerta era de {alert['percent']}%). "
                                      f"{INDICATION_TEXT[alert['indication']]}", event["id"])
                c.execute("UPDATE alertas SET nivel = %s, nivel_desde = now() WHERE id = %s", (level, r["id"]))
                alert = _item(c.fetch_one(SQL + " AND a.id = %s", (r["id"],)))
            rows.append({**alert, "move": move})
    return rows


def created_dates(author):
    """Fechas de las alertas que puso un usuario (constancia del consultor)."""
    return [iso(r["creada_en"]) for r in c.fetch_all(
        "SELECT a.creada_en FROM alertas a JOIN usuarios u ON u.id = a.creada_por WHERE u.usuario = %s", (author,))]
