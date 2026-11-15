"""Wrapper sobre la API SIE de Banxico para tasas de instrumentos gubernamentales.

Se usa el header Bmx-Token en vez de mandar el token en la URL, para que no
quede expuesto en logs de acceso o en el historial del navegador/proxy.
"""
import time
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


_RATES_TTL_SECONDS = 30 * 60
_rates_cache = {}


def _last_valid_rate(datos):
    valid = [d for d in datos if d["dato"] not in ("N/E", "")]
    return _parse_dato(valid[-1]["dato"]) if valid else None


def get_latest_rates(series_ids):
    """Ultima tasa publicada de varias series en UNA sola consulta (Banxico
    limita las consultas por token) y con cache de 30 min: las tasas de las
    subastas cambian una vez por semana. Devuelve {series_id: tasa}."""
    key = tuple(sorted(series_ids))
    cached = _rates_cache.get(key)
    if cached and time.monotonic() - cached[0] < _RATES_TTL_SECONDS:
        return cached[1]

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    url = f"{BASE_URL}/{','.join(key)}/datos/{start_date:%Y-%m-%d}/{end_date:%Y-%m-%d}"

    response = requests.get(url, headers=_headers(), timeout=10)
    response.raise_for_status()

    rates = {}
    for serie in response.json()["bmx"]["series"]:
        rate = _last_valid_rate(serie.get("datos", []))
        if rate is not None:
            rates[serie["idSerie"]] = rate

    _rates_cache[key] = (time.monotonic(), rates)
    return rates


def get_latest_dated(series_id):
    """(valor, fecha) del ultimo dato publicado de una serie. ValueError si no hay datos en los ultimos 30 dias."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    url = f"{BASE_URL}/{series_id}/datos/{start_date:%Y-%m-%d}/{end_date:%Y-%m-%d}"
    response = requests.get(url, headers=_headers(), timeout=10)
    response.raise_for_status()
    valid = [d for d in response.json()["bmx"]["series"][0].get("datos", []) if d["dato"] not in ("N/E", "")]
    if not valid:
        raise ValueError(f"Sin datos recientes para la serie {series_id}")
    day, month, year = valid[-1]["fecha"].split("/")
    return _parse_dato(valid[-1]["dato"]), f"{year}-{month}-{day}"


def get_rate_on(series_id, day):
    """Tasa publicada con la fecha exacta `day`. Banxico etiqueta cada subasta con su fecha de liquidacion; si ese dia
    no hay dato, el instrumento no se subasto esa semana o Banxico todavia no publica el resultado."""
    start_date = day - timedelta(days=7)
    url = f"{BASE_URL}/{series_id}/datos/{start_date:%Y-%m-%d}/{day:%Y-%m-%d}"

    response = requests.get(url, headers=_headers(), timeout=10)
    response.raise_for_status()
    label = f"{day:%d/%m/%Y}"
    for punto in response.json()["bmx"]["series"][0].get("datos", []):
        if punto["fecha"] == label and punto["dato"] not in ("N/E", ""):
            return _parse_dato(punto["dato"])
    raise ValueError(f"Sin tasa publicada para la serie {series_id} el {day}")


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
