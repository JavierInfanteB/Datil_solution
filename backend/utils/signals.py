"""Sugerencias del consultor con la fecha y hora en que aparecieron (signals.json: {cliente: {clave: sugerencia}}).

Las sugerencias se calculan al vuelo desde el riesgo de la cartera; aqui se recuerda cuando se vio cada una por primera
vez y cuando dejo de verse (resuelta), para poder ordenarlas en el tiempo junto con las alertas.
"""
from datetime import datetime, timedelta, timezone

from utils.data_store import read_json, write_json

FILE = "signals.json"
KEEP_DAYS = 30  # cuanto se muestran las ya resueltas


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sync(username, decisions):
    """Actualiza lo guardado del cliente con las sugerencias de hoy y devuelve activas y resueltas recientes."""
    data = read_json(FILE, {})
    saved = data.setdefault(username, {})
    now, today = _now(), {}
    for d in decisions:
        key = f"{d['id']}:{d.get('symbol', '')}"
        today[key] = d
        old = saved.get(key)
        first = now if old is None or old.get("resolved_at") else old["first_seen"]
        saved[key] = {"id": d["id"], "symbol": d.get("symbol"), "severity": d["severity"], "title": d["title"],
                      "detail": d["detail"], "first_seen": first, "resolved_at": None}
    for key, item in saved.items():
        if key not in today and not item.get("resolved_at"):
            item["resolved_at"] = now
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    data[username] = saved = {k: v for k, v in saved.items() if not v.get("resolved_at") or v["resolved_at"] >= cutoff}
    write_json(FILE, data)
    return [{"key": key, **item, "status": "resuelta" if item["resolved_at"] else "activa"} for key, item in saved.items()]
