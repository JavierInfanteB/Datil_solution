"""Aplica database/schema/*.sql a PostgreSQL, en orden y una sola vez cada archivo, y (opcional) importa los JSON.

  python run_migrations.py [--import-json ../../data] [--dry-run]

Variables: DB_HOST, DB_PORT, DB_NAME, POSTGRES_USER, POSTGRES_PASSWORD (propietario), DATIL_APP_PASSWORD y
DATIL_READONLY_PASSWORD (contrasenas de los roles datil_app y datil_readonly; no viven en el repo).
  * Archivos NNN_*.sql: versionados; se aplican una vez y se registra su checksum en datil.schema_migraciones.
  * Archivos R__*.sql: repetibles (permisos); se aplican en cada arranque.
Es idempotente: se puede correr en cada `docker compose up`.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_json  # noqa: E402

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"


def wait_for_database(timeout=90):
    deadline, last = time.time() + timeout, None
    while time.time() < deadline:
        try:
            return import_json.connect()
        except psycopg.OperationalError as exc:
            last = exc
            print("Esperando a PostgreSQL...", str(exc).strip().splitlines()[-1][:100], flush=True)
            time.sleep(2)
    raise SystemExit(f"PostgreSQL no respondio en {timeout}s: {last}")


def apply_schema(conn):
    import os
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--import-json", metavar="DIR", help="carpeta con los JSON originales (data/)")
    parser.add_argument("--dry-run", action="store_true", help="la importacion se simula y se revierte")
    parser.add_argument("--report", help="guarda el reporte de la importacion en esta ruta")
    args = parser.parse_args()
    conn = wait_for_database()
    done = apply_schema(conn)
    print("Esquema:", ", ".join(done) if done else "al dia (nada nuevo que aplicar)")
    if args.import_json:
        report = import_json.run_import(conn, args.import_json, args.dry_run)
        import_json.print_report(report)
        if args.report:
            Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
