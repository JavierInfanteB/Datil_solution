"""Listas de registros por clave (metas, notas): archivo {clave: [registro, ...]}, del mas viejo al mas nuevo."""
import uuid
from datetime import datetime, timezone

from utils.data_store import read_json, write_json


def items(filename, key):
    return read_json(filename, {}).get(key, [])


def add(filename, key, fields):
    data = read_json(filename, {})
    item = {"id": str(uuid.uuid4()), "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}
    data.setdefault(key, []).append(item)
    write_json(filename, data)
    return item


def remove(filename, key, item_id):
    """Borra el registro `item_id` de `key`. False si no existe."""
    data = read_json(filename, {})
    kept = [i for i in data.get(key, []) if i["id"] != item_id]
    if len(kept) == len(data.get(key, [])):
        return False
    data[key] = kept
    write_json(filename, data)
    return True
