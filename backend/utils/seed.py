"""Bootstrap de datos de prueba.

Asegura que el usuario admin (y cualquier otro usuario semilla) tenga una
password hasheada valida, generandola en el primer arranque si hace falta.
Esto evita tener que pre-calcular hashes a mano en el JSON de pruebas.
"""
from werkzeug.security import generate_password_hash

from utils.data_store import read_json, write_json

DEFAULT_ADMIN_PASSWORD = "admin"


def ensure_seed_data():
    users_data = read_json("users.json")
    changed = False

    for user in users_data["users"]:
        if not user.get("password_hash"):
            default_password = DEFAULT_ADMIN_PASSWORD if user["username"] == "admin" else user["username"]
            user["password_hash"] = generate_password_hash(default_password)
            changed = True

    if changed:
        write_json("users.json", users_data)
