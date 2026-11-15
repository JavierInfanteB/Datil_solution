"""Sugerencias del consultor con la fecha y hora en que aparecieron (tabla sugerencias).

Las sugerencias se calculan al vuelo desde el riesgo de la cartera; aqui se recuerda cuando se vio cada una por primera
vez y cuando dejo de verse (resuelta), para poder ordenarlas en el tiempo junto con las alertas. Si una resuelta
reaparece se crea una fila nueva y se conserva el historial (la anterior queda resuelta).
"""
from datetime import datetime, timedelta, timezone

from db import connection as c
from db.connection import iso, transaction
from db.portfolio import ensure_catalog

KEEP_DAYS = 30  # cuanto se muestran las ya resueltas


def sync(username, decisions):
    """Actualiza lo guardado del cliente con las sugerencias de hoy y devuelve activas y resueltas recientes."""
    with transaction():
        client = c.fetch_one("SELECT id FROM usuarios WHERE usuario = %s FOR UPDATE", (username,))["id"]
        now = datetime.now(timezone.utc)
        today = set()
        for d in decisions:
            symbol = d.get("symbol") or None
            today.add((d["id"], symbol or ""))
            if symbol:
                ensure_catalog(symbol, symbol)
            row = c.fetch_one("SELECT id FROM sugerencias WHERE cliente_id = %s AND clave = %s AND COALESCE(simbolo, '') = %s "
                              "AND resuelta_en IS NULL", (client, d["id"], symbol or ""))
            if row is None:
                c.execute("INSERT INTO sugerencias (cliente_id, clave, simbolo, severidad, titulo, detalle, vista_por_primera_vez) "
                          "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                          (client, d["id"], symbol, d["severity"], d["title"][:150], d["detail"], now))
            else:
                c.execute("UPDATE sugerencias SET severidad = %s, titulo = %s, detalle = %s WHERE id = %s",
                          (d["severity"], d["title"][:150], d["detail"], row["id"]))
        for r in c.fetch_all("SELECT id, clave, COALESCE(simbolo, '') AS simbolo FROM sugerencias WHERE cliente_id = %s AND resuelta_en IS NULL", (client,)):
            if (r["clave"], r["simbolo"]) not in today:
                c.execute("UPDATE sugerencias SET resuelta_en = %s WHERE id = %s", (now, r["id"]))
        cutoff = now - timedelta(days=KEEP_DAYS)
        rows = c.fetch_all(
            "SELECT DISTINCT ON (clave, COALESCE(simbolo, '')) clave, simbolo, severidad, titulo, detalle, vista_por_primera_vez, resuelta_en "
            "FROM sugerencias WHERE cliente_id = %s AND (resuelta_en IS NULL OR resuelta_en >= %s) "
            "ORDER BY clave, COALESCE(simbolo, ''), vista_por_primera_vez DESC, id DESC", (client, cutoff))
    return [{"key": f"{r['clave']}:{r['simbolo'] or ''}", "id": r["clave"], "symbol": r["simbolo"], "severity": r["severidad"],
             "title": r["titulo"], "detail": r["detalle"], "first_seen": iso(r["vista_por_primera_vez"]),
             "resolved_at": iso(r["resuelta_en"]), "status": "resuelta" if r["resuelta_en"] else "activa"} for r in rows]
