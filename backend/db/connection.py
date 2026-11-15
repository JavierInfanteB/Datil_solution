"""Conexion a PostgreSQL por variables de entorno, una conexion por peticion y transacciones explicitas.

Variables: DATABASE_URL (opcional, gana sobre las demas) o DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.
La conexion usa autocommit: cada sentencia suelta se confirma sola y todo lo que debe ser atomico va dentro de
`with transaction():` (BEGIN/COMMIT; anidada = SAVEPOINT).
"""
import logging
import os
import threading
import time
from contextlib import contextmanager
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger("datil.db")

CONNECT_RETRIES = 3
CONNECT_TIMEOUT = 5  # segundos por intento


class DatabaseUnavailable(Exception):
    """No hay conexion con PostgreSQL (la API responde 503)."""


def _settings():
    url = os.environ.get("DATABASE_URL")
    kwargs = {"options": "-c search_path=datil,public -c timezone=UTC", "connect_timeout": CONNECT_TIMEOUT,
              "application_name": "datil-api"}
    if url:
        return url, kwargs
    kwargs.update(
        host=os.environ.get("DB_HOST", "localhost"), port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "datil_db"), user=os.environ.get("DB_USER", "datil_app"),
        password=os.environ.get("DB_PASSWORD", ""),
    )
    return "", kwargs


class _State:
    """Conexion + profundidad de transaccion. Una por hilo (y una por peticion Flask)."""
    __slots__ = ("conn", "depth")

    def __init__(self):
        self.conn, self.depth = None, 0


_local = threading.local()


def _state():
    if not hasattr(_local, "state"):
        _local.state = _State()
    return _local.state


def _connect():
    conninfo, kwargs = _settings()
    last = None
    for attempt in range(1, CONNECT_RETRIES + 1):
        try:
            return psycopg.connect(conninfo, autocommit=True, row_factory=dict_row, **kwargs)
        except psycopg.OperationalError as exc:
            last = exc
            log.warning("Sin conexion a PostgreSQL (intento %s/%s): %s", attempt, CONNECT_RETRIES, str(exc).strip()[:160])
            time.sleep(0.4 * attempt)
    raise DatabaseUnavailable(str(last))


def _conn():
    st = _state()
    if st.conn is None or st.conn.closed:
        st.conn, st.depth = _connect(), 0
    return st.conn


def close_connection(*_):
    st = _state()
    if st.conn is not None and not st.conn.closed:
        try:
            st.conn.close()
        except psycopg.Error:
            pass
    st.conn, st.depth = None, 0


def init_app(app):
    """Cierra la conexion del hilo al terminar cada peticion y traduce los fallos de base de datos a JSON."""
    from flask import jsonify

    app.teardown_appcontext(close_connection)

    @app.errorhandler(DatabaseUnavailable)
    def _unavailable(_exc):
        return jsonify({"error": "Base de datos no disponible. Intenta de nuevo en unos segundos"}), 503

    @app.errorhandler(psycopg.OperationalError)
    def _operational(exc):
        log.error("Fallo de PostgreSQL: %s", exc)
        return jsonify({"error": "Base de datos no disponible. Intenta de nuevo en unos segundos"}), 503

    @app.errorhandler(psycopg.Error)
    def _database_error(exc):
        log.exception("Error de base de datos: %s", exc)
        return jsonify({"error": "Error interno de base de datos; la operacion no se aplico"}), 500


def _run(sql, params):
    """Ejecuta una sentencia; si la conexion murio fuera de una transaccion, reconecta y reintenta una vez."""
    for retry in (True, False):
        conn = _conn()
        try:
            return conn.execute(sql, params)
        except psycopg.OperationalError:
            if _state().depth or not retry:
                close_connection()
                raise DatabaseUnavailable("Se perdio la conexion con PostgreSQL")
            close_connection()


def fetch_all(sql, params=()):
    return _run(sql, params).fetchall()


def fetch_one(sql, params=()):
    return _run(sql, params).fetchone()


def execute(sql, params=()):
    """Devuelve el numero de filas afectadas."""
    return _run(sql, params).rowcount


@contextmanager
def transaction():
    """Bloque atomico: todo o nada. Anidado se vuelve SAVEPOINT."""
    conn, st = _conn(), _state()
    try:
        with conn.transaction():
            st.depth += 1
            try:
                yield conn
            finally:
                st.depth -= 1
    except psycopg.OperationalError as exc:
        close_connection()
        raise DatabaseUnavailable(str(exc))


def ping():
    try:
        return fetch_one("SELECT 1 AS ok")["ok"] == 1
    except (DatabaseUnavailable, psycopg.Error):
        return False


# -------------------------------------------------------------- conversiones
def as_float(value):
    """NUMERIC (Decimal) -> float para el motor financiero y el JSON; None se queda None."""
    return None if value is None else float(value)


def as_num(value):
    """Cantidades: entero cuando no tiene decimales (el JSON original traia 18 y no 18.0), si no float."""
    if value is None:
        return None
    value = Decimal(value)
    return int(value) if value == value.to_integral_value() else float(value)


def iso(moment):
    """datetime -> '2026-10-27T15:00:00+00:00' (mismo formato de los JSON originales)."""
    if moment is None:
        return None
    from datetime import timezone
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")
