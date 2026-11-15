"""Despliega Datil en el Docker de esta PC: construye la imagen con este commit y recrea el contenedor.
Antes de arrancar, compose levanta la base (db) y corre las migraciones (migrate) con esa misma imagen.

Lo corre el runner (.github/workflows/deploy.yml) y es lo mismo que se hacia a mano:
`docker compose up -d --build web` en 08_Web/datil/, pero desde el checkout del commit.
Recrear el contenedor cierra las sesiones abiertas (viven en memoria del proceso).
"""
import os
import subprocess
import sys
import time
import urllib.request
import winreg
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMPOSE = os.environ.get("DATIL_COMPOSE", r"C:\Users\bonan\OneDrive\Documentos\Proyectos_bonais\08_Web\datil\docker-compose.yml")
OVERRIDE = Path(__file__).with_name("compose.override.yml")
CONTAINER = "datil-web-1"
URL = "http://localhost:5002/"


# Claves opcionales que tambien viven como variables de usuario: asistente, bot de Telegram y cifrado de datos personales.
OPTIONAL_VARS = ("IA_DATIL", "TELEGRAM_DATIL", "CIFRADO_DATIL")


def user_var(name):
    """Las claves viven solo como variables de usuario de Windows (no en 08_Web/datil/.env, que se sincroniza a OneDrive).
    Se leen del registro y no del entorno del proceso, que puede ser anterior a que se definieran."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return os.environ.get(name, "")


def banxico_token():
    return user_var("BANXICO_TOKEN")


def main():
    token = banxico_token()
    if not token:
        sys.exit("Falta BANXICO_TOKEN como variable de usuario: sin el, el contenedor quedaria sin token. No se despliega.")

    env = {**os.environ, "BANXICO_TOKEN": token, "DATIL_SRC": REPO.as_posix(), **{name: user_var(name) for name in OPTIONAL_VARS}}
    subprocess.run(["docker", "compose", "-f", COMPOSE, "-f", str(OVERRIDE), "up", "-d", "--build", "web"], env=env, check=True)

    # Que el contenedor haya recibido el token, sin imprimirlo
    subprocess.run(["docker", "exec", CONTAINER, "sh", "-c", 'test -n "$BANXICO_TOKEN"'], check=True)

    for _ in range(45):
        try:
            if urllib.request.urlopen(URL, timeout=5).status == 200:
                print(f"Datil responde en {URL} (commit {os.environ.get('GITHUB_SHA', 'local')[:7]})")
                return
        except OSError:
            pass
        time.sleep(2)
    sys.exit(f"El contenedor no respondio en {URL} tras 90 s")


if __name__ == "__main__":
    main()
