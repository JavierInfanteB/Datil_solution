"""Wrapper sobre la API SIE de Banxico para tasas de instrumentos gubernamentales.

Se usa el header Bmx-Token en vez de mandar el token en la URL, para que no
quede expuesto en logs de acceso o en el historial del navegador/proxy.
"""
from datetime import datetime, timedelta

import requests

from config import Config

BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"


def _headers():
    return {"Bmx-Token": Config.BANXICO_TOKEN}


def _parse_dato(valor):
    return float(valor.replace(",", ""))


def get_bond_rate(series_id, symbol):
    """Ultima tasa publicada y la anterior, para calcular variacion (sube/baja)."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    url = f"{BASE_URL}/{series_id}/datos/{start_date:%Y-%m-%d}/{end_date:%Y-%m-%d}"

    response = requests.get(url, headers=_headers(), timeout=10)
    response.raise_for_status()
    datos = [d for d in response.json()["bmx"]["series"][0]["datos"] if d["dato"] not in ("N/E", "")]

    if not datos:
        raise ValueError(f"Sin datos recientes para la serie {series_id}")

    latest = datos[-1]
    previous = datos[-2] if len(datos) > 1 else latest

    rate = _parse_dato(latest["dato"])
    previous_rate = _parse_dato(previous["dato"])
    change = rate - previous_rate
    change_percent = (change / previous_rate * 100) if previous_rate else 0

    return {
        "symbol": symbol,
        "price": round(rate, 4),
        "previous_close": round(previous_rate, 4),
        "change": round(change, 4),
        "change_percent": round(change_percent, 2),
        "change_period": "1w",
    }


def get_bond_history(series_id, days=180):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    url = f"{BASE_URL}/{series_id}/datos/{start_date:%Y-%m-%d}/{end_date:%Y-%m-%d}"

    response = requests.get(url, headers=_headers(), timeout=10)
    response.raise_for_status()
    datos = response.json()["bmx"]["series"][0]["datos"]

    history = []
    for punto in datos:
        if punto["dato"] in ("N/E", ""):
            continue
        day, month, year = punto["fecha"].split("/")
        history.append({
            "date": f"{year}-{month}-{day}",
            "close": round(_parse_dato(punto["dato"]), 4),
        })
    return history
