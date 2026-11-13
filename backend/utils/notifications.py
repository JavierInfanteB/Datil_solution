"""Avisos del consultor a sus clientes y del sistema (tabla avisos)."""
from db import connection as c
from db.connection import iso

KINDS = ("aviso", "riesgo", "accion")  # aviso general, alerta de riesgo, accion sugerida
ALERT = "alerta"  # lo genera el sistema cuando se cumple una alerta del cliente; el consultor no lo manda

SQL = ("SELECT a.uid, a.fecha_hora, a.tipo, a.titulo, a.mensaje, a.leido, cl.usuario AS cliente, de.usuario AS de, de.nombre AS de_nombre "
       "FROM avisos a JOIN usuarios cl ON cl.id = a.cliente_id LEFT JOIN usuarios de ON de.id = a.de_usuario_id")


def _item(r):
    return {"id": str(r["uid"]), "date": iso(r["fecha_hora"]), "from": r["de"] or "sistema",
            "from_name": r["de_nombre"] or "Datil Solution", "kind": r["tipo"], "title": r["titulo"],
            "message": r["mensaje"], "read": r["leido"]}


def load(recipient=None):
    """{usuario: [aviso, ...]} del mas viejo al mas nuevo; con `recipient`, solo ese usuario (la llave siempre existe)."""
    rows = c.fetch_all(SQL + (" WHERE cl.usuario = %s" if recipient else "") + " ORDER BY a.fecha_hora, a.id",
                       (recipient,) if recipient else ())
    data = {recipient: []} if recipient else {}
    for r in rows:
        data.setdefault(r["cliente"], []).append(_item(r))
    return data


def add(recipient, sender, kind, title, message, event_id=None):
    """Guarda un aviso de `sender` (dict con username y name) para el usuario `recipient`. El sistema no tiene fila de usuario."""
    row = c.fetch_one(
        "INSERT INTO avisos (cliente_id, de_usuario_id, tipo, titulo, mensaje, evento_alerta_id) "
        "VALUES ((SELECT id FROM usuarios WHERE usuario = %s), (SELECT id FROM usuarios WHERE usuario = %s), %s, %s, %s, %s) "
        "RETURNING uid", (recipient, sender["username"], kind, title, message, event_id))
    return _item(c.fetch_one(SQL + " WHERE a.uid = %s", (row["uid"],)))


def mark_read(recipient, notification_id):
    """Marca como leido un aviso del usuario; None si no existe."""
    n = c.execute("UPDATE avisos SET leido = TRUE, leido_en = COALESCE(leido_en, now()) "
                  "WHERE uid::text = %s AND cliente_id = (SELECT id FROM usuarios WHERE usuario = %s)", (notification_id, recipient))
    if not n:
        return None
    return _item(c.fetch_one(SQL + " WHERE a.uid::text = %s", (notification_id,)))


def sent_dates(sender):
    """Fechas de los avisos que mando un usuario (constancia del consultor)."""
    return [iso(r["fecha_hora"]) for r in c.fetch_all(
        "SELECT a.fecha_hora FROM avisos a JOIN usuarios u ON u.id = a.de_usuario_id WHERE u.usuario = %s", (sender,))]
