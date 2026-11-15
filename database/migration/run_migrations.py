"""Aplica database/schema/*.sql a PostgreSQL, en orden y una sola vez cada archivo.

  python run_migrations.py

Variables: DB_HOST, DB_PORT, DB_NAME, POSTGRES_USER, POSTGRES_PASSWORD (propietario), DATIL_APP_PASSWORD y
DATIL_READONLY_PASSWORD (contrasenas de los roles datil_app y datil_readonly; no viven en el repo).
  * Archivos NNN_*.sql: versionados; se aplican una vez y se registra su checksum en datil.schema_migraciones.
  * Archivos R__*.sql: repetibles (permisos); se aplican en cada arranque.
Es idempotente: se puede correr en cada `docker compose up`. La importacion de los JSON originales vive en la rama `pruebas`.
"""
import hashlib
import os
import sys
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"


def connect():
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "localhost"), port=os.environ.get("DB_PORT", "5432"), dbname=os.environ.get("DB_NAME", "datil_db"),
        user=os.environ.get("POSTGRES_USER", "datil_owner"), password=os.environ.get("POSTGRES_PASSWORD", ""),
        options="-c search_path=datil,public -c timezone=UTC", autocommit=True, row_factory=dict_row)


def wait_for_database(timeout=90):
    deadline, last = time.time() + timeout, None
    while time.time() < deadline:
        try:
            return connect()
        except psycopg.OperationalError as exc:
            last = exc
            print("Esperando a PostgreSQL...", str(exc).strip().splitlines()[-1][:100], flush=True)
            time.sleep(2)
    raise SystemExit(f"PostgreSQL no respondio en {timeout}s: {last}")


def apply_schema(conn):
    conn.execute("CREATE SCHEMA IF NOT EXISTS datil")
    conn.execute("CREATE TABLE IF NOT EXISTS datil.schema_migraciones (version TEXT PRIMARY KEY, checksum TEXT NOT NULL, "
                 "aplicada_en TIMESTAMPTZ NOT NULL DEFAULT now())")
    applied = {r["version"]: r["checksum"] for r in conn.execute("SELECT version, checksum FROM datil.schema_migraciones").fetchall()}
    done = []
    for path in sorted(SCHEMA_DIR.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(text.encode()).hexdigest()
        if path.name.startswith("R__"):
            conn.execute("SELECT set_config('datil.app_password', %s, false), set_config('datil.readonly_password', %s, false)",
                         (os.environ.get("DATIL_APP_PASSWORD", ""), os.environ.get("DATIL_READONLY_PASSWORD", "")))
            conn.execute(text)
            done.append(f"{path.name} (repetible)")
            continue
        if path.name in applied:
            if applied[path.name] != checksum:
                print(f"AVISO: {path.name} cambio despues de aplicarse; no se vuelve a ejecutar (crea un archivo nuevo para cambios).")
            continue
        with conn.transaction():
            conn.execute(text)
            conn.execute("INSERT INTO datil.schema_migraciones (version, checksum) VALUES (%s, %s)", (path.name, checksum))
        done.append(path.name)
    return done


def main():
    conn = wait_for_database()
    done = apply_schema(conn)
    print("Esquema:", ", ".join(done) if done else "al dia (nada nuevo que aplicar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
