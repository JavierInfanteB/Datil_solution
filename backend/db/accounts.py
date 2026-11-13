"""Usuarios, puestos, permisos, asignaciones de consultor, sesiones e intentos de login."""
from datetime import date, datetime, timezone

import psycopg

from db import connection as c

USER_SQL = """
SELECT u.id, u.usuario, u.nombre, u.rol, u.estado, u.contrasena_hash, p.nombre AS puesto,
       (SELECT k.usuario FROM asignaciones_consultor a JOIN usuarios k ON k.id = a.consultor_id
         WHERE a.cliente_id = u.id AND a.hasta IS NULL) AS consultor
  FROM usuarios u LEFT JOIN puestos p ON p.id = u.puesto_id
"""


def _legacy(row):
    """Fila de BD -> dict con la misma forma que tenia users.json (username, name, role, puesto, consultant...)."""
    if row is None:
        return None
    return {"id": row["id"], "username": row["usuario"], "name": row["nombre"], "role": row["rol"],
            "password_hash": row["contrasena_hash"], "puesto": row["puesto"], "consultant": row["consultor"],
            "disabled": row["estado"] != "activo", "deleted": row["estado"] == "baja"}


def list_users():
    return [_legacy(r) for r in c.fetch_all(USER_SQL + " ORDER BY u.id")]


def get_user(*, username=None, id=None):
    if username is not None:
        return _legacy(c.fetch_one(USER_SQL + " WHERE u.usuario = %s", (username,)))
    return _legacy(c.fetch_one(USER_SQL + " WHERE u.id = %s", (id,)))


def clients_of(consultant):
    return [_legacy(r) for r in c.fetch_all(
        USER_SQL + " WHERE u.rol = 'usuario' AND EXISTS (SELECT 1 FROM asignaciones_consultor a JOIN usuarios k "
                   "ON k.id = a.consultor_id WHERE a.cliente_id = u.id AND a.hasta IS NULL AND k.usuario = %s) ORDER BY u.id",
        (consultant,))]


# ---------------------------------------------------------------- permisos y puestos
def own_permissions(username):
    row = c.fetch_one("SELECT permisos FROM usuarios WHERE usuario = %s", (username,))
    return list(row["permisos"]) if row else []


def all_permissions():
    """{usuario: [permisos propios]} de quienes tienen alguno (como permissions.json)."""
    return {r["usuario"]: list(r["permisos"]) for r in c.fetch_all(
        "SELECT usuario, permisos FROM usuarios WHERE cardinality(permisos) > 0 ORDER BY id")}


def set_permissions(username, modules):
    c.execute("UPDATE usuarios SET permisos = %s WHERE usuario = %s", (list(modules), username))


def load_puestos():
    return {r["nombre"]: list(r["permisos"]) for r in c.fetch_all("SELECT nombre, permisos FROM puestos ORDER BY id")}


def save_puesto(name, modules):
    c.execute("INSERT INTO puestos (nombre, permisos) VALUES (%s, %s) ON CONFLICT (nombre) DO UPDATE SET permisos = EXCLUDED.permisos",
              (name, list(modules)))


def delete_puesto(name):
    c.execute("DELETE FROM puestos WHERE nombre = %s", (name,))


def puesto_in_use(name):
    return c.fetch_one("SELECT 1 AS x FROM usuarios u JOIN puestos p ON p.id = u.puesto_id WHERE p.nombre = %s LIMIT 1",
                       (name,)) is not None


# ---------------------------------------------------------------- altas y cambios (admin)
class UserExists(Exception):
    pass


def create_user(username, name, password_hash, role, puesto=None, created_by=None):
    """Crea el usuario y devuelve su dict legacy. UserExists si el nombre ya esta tomado."""
    try:
        row = c.fetch_one(
            "INSERT INTO usuarios (usuario, nombre, contrasena_hash, rol, puesto_id, creado_por) "
            "VALUES (%s, %s, %s, %s, (SELECT id FROM puestos WHERE nombre = %s), %s) RETURNING id",
            (username, name, password_hash, role, puesto, created_by))
    except psycopg.errors.UniqueViolation:
        raise UserExists(username)
    return get_user(id=row["id"])


def set_password(username, password_hash):
    c.execute("UPDATE usuarios SET contrasena_hash = %s, contrasena_cambiada_en = now() WHERE usuario = %s",
              (password_hash, username))


def set_name(username, name):
    c.execute("UPDATE usuarios SET nombre = %s WHERE usuario = %s", (name, username))


def set_state(username, state):
    """state: 'activo' | 'suspendido' | 'baja'."""
    c.execute("UPDATE usuarios SET estado = %s, baja_en = CASE WHEN %s = 'baja' THEN now() ELSE NULL END WHERE usuario = %s",
              (state, state, username))


def set_role(username, role):
    c.execute("UPDATE usuarios SET rol = %s WHERE usuario = %s", (role, username))


def set_puesto(username, puesto):
    c.execute("UPDATE usuarios SET puesto_id = (SELECT id FROM puestos WHERE nombre = %s) WHERE usuario = %s",
              (puesto, username))


def set_consultant(username, consultant, assigned_by=None):
    """Cierra la asignacion vigente del cliente y abre otra (historial). consultant=None solo la cierra."""
    today = date.today()
    c.execute("UPDATE asignaciones_consultor SET hasta = %s WHERE hasta IS NULL AND cliente_id = (SELECT id FROM usuarios WHERE usuario = %s)",
              (today, username))
    if consultant:
        c.execute("INSERT INTO asignaciones_consultor (cliente_id, consultor_id, desde, asignado_por) "
                  "SELECT cl.id, co.id, %s, %s FROM usuarios cl, usuarios co WHERE cl.usuario = %s AND co.usuario = %s",
                  (today, assigned_by, username, consultant))


def release_clients_of(consultant):
    """Un consultor que deja de serlo suelta a sus clientes."""
    c.execute("UPDATE asignaciones_consultor SET hasta = %s WHERE hasta IS NULL AND consultor_id = (SELECT id FROM usuarios WHERE usuario = %s)",
              (date.today(), consultant))


def current_consultant(username):
    row = c.fetch_one("SELECT k.usuario FROM asignaciones_consultor a JOIN usuarios k ON k.id = a.consultor_id "
                      "JOIN usuarios cl ON cl.id = a.cliente_id WHERE cl.usuario = %s AND a.hasta IS NULL", (username,))
    return row["usuario"] if row else None


# ---------------------------------------------------------------- sesiones (JWT con inactividad)
def session_create(jti, user_id, ip, device):
    c.execute("INSERT INTO sesiones (jti, usuario_id, ip, dispositivo) VALUES (%s, %s, %s, %s)",
              (jti, user_id, (ip or "0.0.0.0")[:45], (device or "")[:150] or None))


def session_last_activity(jti):
    """Ultima actividad de una sesion abierta; None si no existe o ya se cerro."""
    try:
        row = c.fetch_one("SELECT ultima_actividad FROM sesiones WHERE jti = %s AND cerrada_en IS NULL", (jti,))
    except psycopg.Error:  # jti con formato invalido
        return None
    return row["ultima_actividad"] if row else None


def session_touch(jti):
    c.execute("UPDATE sesiones SET ultima_actividad = now() WHERE jti = %s AND cerrada_en IS NULL", (jti,))


def session_end(jti):
    c.execute("UPDATE sesiones SET cerrada_en = now() WHERE jti = %s AND cerrada_en IS NULL", (jti,))


def is_new_ip(user_id, ip):
    """Una IP es nueva si el usuario no tiene una sesion anterior con ella (el login actual ya se guardo)."""
    row = c.fetch_one("SELECT count(*) AS n FROM sesiones WHERE usuario_id = %s AND ip = %s", (user_id, ip))
    return row["n"] <= 1


def log_login_attempt(typed, user_id, ok, ip, reason=None):
    c.execute("INSERT INTO intentos_login (usuario_escrito, usuario_id, exitoso, ip, motivo_fallo) VALUES (%s, %s, %s, %s, %s)",
              ((typed or "")[:50] or None, user_id, ok, (ip or "0.0.0.0")[:45], reason))


def now():
    return datetime.now(timezone.utc)
