"""Configuracion global de la aplicacion Datil Solutions."""
import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Carga backend/.env (secretos y tokens NO viven en el codigo fuente).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


# Modo demo: la API solo lee. Ninguna ruta ni evento programado modifica la base de datos.
DEMO_READONLY = os.environ.get("DEMO_READONLY") == "1"


class Config:
    # En produccion esto DEBE venir de una variable de entorno real.
    SECRET_KEY = os.environ.get("SECRET_KEY", "datil-solutions-dev-secret-change-in-prod")

    # Ventana de inactividad: se reinicia con cada peticion autenticada.
    SESSION_TIMEOUT = timedelta(minutes=10)
    # Tope absoluto de vida del token, independiente de la actividad.
    TOKEN_MAX_AGE = timedelta(hours=8)

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

    # Token de consulta de la API SIE de Banxico (tasas de CETES / Bono M).
    BANXICO_TOKEN = os.environ.get("BANXICO_TOKEN", "")

    # Token del bot de Telegram que manda los avisos (variable de entorno TELEGRAM_DATIL); vacio = sin Telegram.
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_DATIL", "")

    # Clave de cifrado de datos personales (32 bytes en base64, variable CIFRADO_DATIL); ver utils/cifrado.py.
    CIFRADO_KEY = os.environ.get("CIFRADO_DATIL", "")

    # Clave de Google AI Studio para el agente: variable de entorno IA_DATIL (GEMINI_API_KEY como respaldo).
    GEMINI_API_KEY = os.environ.get("IA_DATIL") or os.environ.get("GEMINI_API_KEY", "")

    # Carpeta con el frontend compilado: si existe, Flask lo sirve en "/" (web y API en un solo dominio).
    STATIC_DIR = os.environ.get("STATIC_DIR") or None


# Base de datos (PostgreSQL 16): se configura con variables de entorno, ver .env.example en la raiz del proyecto.
#   DATABASE_URL, o bien DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD (lee db/connection.py).
