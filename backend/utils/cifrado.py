"""Cifrado de datos personales antes de guardarlos en la base (hoy: el chat de Telegram de cada usuario).

Mismo esquema que la boveda del proyecto de criptografia: AES-256-GCM con un nonce aleatorio de 12 bytes por valor y
datos asociados (AAD) que se autentican sin cifrarse. Aqui el AAD es el contexto del dato (tabla, columna y id de la
fila): un valor copiado a la fila de otro usuario no descifra. Lo que se guarda es texto: "v1:" + base64(nonce + cifrado).

La clave no vive en la base ni en el repo: 32 bytes en base64 en la variable de entorno CIFRADO_DATIL. Generarla:
    python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
Sin clave no se guarda nada (nunca en claro). Si se pierde la clave, lo cifrado no se recupera: los usuarios vuelven a enlazar.
"""
import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import Config

PREFIX = "v1:"


class CifradoError(Exception):
    """No hay clave valida, o el valor guardado fue alterado o es de otra clave o de otra fila."""


def _clave():
    try:
        key = base64.b64decode(Config.CIFRADO_KEY or "", validate=True)
    except (binascii.Error, ValueError):
        key = b""
    if len(key) != 32:
        raise CifradoError("CIFRADO_DATIL debe ser una clave de 32 bytes en base64")
    return key


def disponible() -> bool:
    try:
        _clave()
        return True
    except CifradoError:
        return False


def cifrar(texto: str, contexto: str) -> str:
    nonce = os.urandom(12)  # nunca se repite con la misma clave
    cifrado = AESGCM(_clave()).encrypt(nonce, texto.encode(), contexto.encode())
    return PREFIX + base64.b64encode(nonce + cifrado).decode()


def descifrar(valor: str, contexto: str) -> str:
    if not valor.startswith(PREFIX):
        raise CifradoError("Valor sin el formato de cifrado esperado")
    try:
        raw = base64.b64decode(valor[len(PREFIX):], validate=True)
        return AESGCM(_clave()).decrypt(raw[:12], raw[12:], contexto.encode()).decode()
    except (InvalidTag, binascii.Error, ValueError) as e:
        raise CifradoError("No se pudo descifrar el valor") from e
