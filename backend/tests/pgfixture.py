"""Base de datos de pruebas: PostgreSQL real, nunca los JSON ni la base de desarrollo.

Variables (por defecto las mismas DB_*): TEST_DB_HOST, TEST_DB_PORT, TEST_DB_NAME (OBLIGATORIA y distinta de la de
desarrollo: el esquema se BORRA y se recrea), POSTGRES_USER/POSTGRES_PASSWORD (propietario), DATIL_APP_PASSWORD.
La app corre con el rol datil_app, igual que en produccion, de modo que las pruebas ejercen los permisos reales.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "database" / "migration"))
sys.path.insert(0, str(ROOT / "backend"))

import import_json  # noqa: E402
import run_migrations  # noqa: E402

APP_PASSWORD = os.environ.get("DATIL_APP_PASSWORD") or "clave-app-de-prueba"
RO_PASSWORD = os.environ.get("DATIL_READONLY_PASSWORD") or "clave-ro-de-prueba"
# Tablas que los seeds de 060 llenan y que las pruebas conservan.
KEEP = {"series_mercado", "instrumentos", "dias_inhabiles", "schema_migraciones", "acciones_catalogo"}
_ready = False


def configured():
    return bool(os.environ.get("TEST_DB_NAME"))


def owner_conn():
    return psycopg.connect(
        host=os.environ.get("TEST_DB_HOST", os.environ.get("DB_HOST", "localhost")),
        port=os.environ.get("TEST_DB_PORT", os.environ.get("DB_PORT", "5432")), dbname=os.environ["TEST_DB_NAME"],
        user=os.environ.get("POSTGRES_USER", "datil_owner"), password=os.environ.get("POSTGRES_PASSWORD", ""),
        options="-c search_path=datil,public -c timezone=UTC", autocommit=True, row_factory=dict_row)


def point_app_at_test_db():
    os.environ.update(DB_HOST=os.environ.get("TEST_DB_HOST", os.environ.get("DB_HOST", "localhost")),
                      DB_PORT=os.environ.get("TEST_DB_PORT", os.environ.get("DB_PORT", "5432")),
                      DB_NAME=os.environ["TEST_DB_NAME"], DB_USER="datil_app", DB_PASSWORD=APP_PASSWORD)


def ensure_schema():
    """Recrea el esquema una vez por proceso con los mismos archivos SQL que usa produccion."""
    global _ready
    if _ready:
        return
    os.environ["DATIL_APP_PASSWORD"], os.environ["DATIL_READONLY_PASSWORD"] = APP_PASSWORD, RO_PASSWORD
    with owner_conn() as conn:
        conn.execute("DROP SCHEMA IF EXISTS datil CASCADE")
        run_migrations.apply_schema(conn)
    point_app_at_test_db()
    _ready = True


def wipe(conn):
    tables = [r["tablename"] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'datil'").fetchall()
              if r["tablename"] not in KEEP]
    conn.execute("SET session_replication_role = replica")  # las tablas inmutables solo se vacian desde aqui, no desde la app
    conn.execute("TRUNCATE " + ", ".join(f'datil."{t}"' for t in tables) + " RESTART IDENTITY CASCADE")
    conn.execute("SET session_replication_role = origin")
    seed = (ROOT / "database" / "schema" / "060_datos_iniciales.sql").read_text(encoding="utf-8")
    start = seed.index("INSERT INTO puestos")
    conn.execute(seed[start:seed.index(";", start) + 1])  # los puestos vuelven a ser los de arranque


def load_json_files(files):
    """Siembra la base con el mismo formato de los JSON originales (pasa por el importador real)."""
    with owner_conn() as conn, tempfile.TemporaryDirectory() as tmp:
        wipe(conn)
        for name, content in files.items():
            Path(tmp, name).write_text(json.dumps(content), encoding="utf-8")
        report = import_json.run_import(conn, tmp)
    return report
