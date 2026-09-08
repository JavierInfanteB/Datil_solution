"""Lectura/escritura de los JSON provisionales que hacen de 'base de datos'."""
import json
import os
import threading

from config import DATA_DIR

# Un lock simple basta: es una app de un solo proceso para desarrollo/demo.
_lock = threading.Lock()


def _path(filename):
    return os.path.join(DATA_DIR, filename)


def read_json(filename):
    with _lock:
        with open(_path(filename), "r", encoding="utf-8") as f:
            return json.load(f)


def write_json(filename, data):
    with _lock:
        with open(_path(filename), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
