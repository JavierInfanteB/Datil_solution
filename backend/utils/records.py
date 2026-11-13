"""Metas y notas (tablas metas y notas). Conserva la interfaz de siempre: (archivo, clave) -> registros.

  goals.json            clave = usuario                -> metas del cliente
  notes.json            clave = usuario                -> notas del cliente para su consultor (no privadas)
  consultant_notes.json clave = "consultor/cliente"    -> notas privadas del consultor (solo las ve quien las escribio)
Cada registro sale como antes: {id, date, ...campos}, del mas viejo al mas nuevo.
"""
from db import connection as c
from db.connection import as_float, iso

GOALS, NOTES, PRIVATE_NOTES = "goals.json", "notes.json", "consultant_notes.json"


def _user_id(username):
    row = c.fetch_one("SELECT id FROM usuarios WHERE usuario = %s", (username,))
    return row["id"] if row else None


def _split(filename, key):
    """(cliente, autor, privada) de la clave."""
    if filename == PRIVATE_NOTES:
        author, client = key.split("/", 1)
        return client, author, True
    return key, key, False


def items(filename, key):
    client, author, private = _split(filename, key)
    if filename == GOALS:
        rows = c.fetch_all("SELECT m.uid, m.creada_en, m.titulo, m.monto_objetivo, m.fecha_objetivo FROM metas m "
                           "JOIN usuarios u ON u.id = m.cliente_id WHERE u.usuario = %s ORDER BY m.creada_en, m.id", (client,))
        out = []
        for r in rows:
            item = {"id": str(r["uid"]), "date": iso(r["creada_en"]), "title": r["titulo"], "target_mxn": as_float(r["monto_objetivo"])}
            if r["fecha_objetivo"]:
                item["target_date"] = r["fecha_objetivo"].isoformat()
            out.append(item)
        return out
    rows = c.fetch_all("SELECT n.uid, n.fecha_hora, n.texto FROM notas n JOIN usuarios u ON u.id = n.cliente_id "
                       "JOIN usuarios a ON a.id = n.autor_id WHERE u.usuario = %s AND a.usuario = %s AND n.privada = %s "
                       "ORDER BY n.fecha_hora, n.id", (client, author, private))
    return [{"id": str(r["uid"]), "date": iso(r["fecha_hora"]), "text": r["texto"]} for r in rows]


def add(filename, key, fields):
    client, author, private = _split(filename, key)
    if filename == GOALS:
        row = c.fetch_one(
            "INSERT INTO metas (cliente_id, titulo, monto_objetivo, fecha_objetivo) VALUES (%s, %s, %s, %s) RETURNING uid, creada_en",
            (_user_id(client), fields["title"], fields["target_mxn"], fields.get("target_date")))
        return {"id": str(row["uid"]), "date": iso(row["creada_en"]), **fields}
    row = c.fetch_one("INSERT INTO notas (cliente_id, autor_id, privada, texto) VALUES (%s, %s, %s, %s) RETURNING uid, fecha_hora",
                      (_user_id(client), _user_id(author), private, fields["text"]))
    return {"id": str(row["uid"]), "date": iso(row["fecha_hora"]), **fields}


def remove(filename, key, item_id):
    """Borra el registro `item_id` de `key`. False si no existe."""
    client, author, private = _split(filename, key)
    if filename == GOALS:
        return c.execute("DELETE FROM metas WHERE uid::text = %s AND cliente_id = %s", (item_id, _user_id(client))) > 0
    return c.execute("DELETE FROM notas WHERE uid::text = %s AND cliente_id = %s AND autor_id = %s AND privada = %s",
                     (item_id, _user_id(client), _user_id(author), private)) > 0


def note_dates(consultant):
    """Fechas de las notas privadas que escribio un consultor (para su constancia en el panel del admin)."""
    return [iso(r["fecha_hora"]) for r in c.fetch_all(
        "SELECT n.fecha_hora FROM notas n JOIN usuarios a ON a.id = n.autor_id WHERE a.usuario = %s AND n.privada", (consultant,))]
