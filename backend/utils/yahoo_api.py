"""Wrapper sobre la API de graficas de Yahoo Finance para precios e historicos.

Se llama directo al endpoint de graficas (chart) con curl_cffi impersonando
un navegador real, en vez de usar yfinance: la libreria yfinance no siempre
respeta la sesion personalizada que se le pasa, lo que termina disparando
el bloqueo anti-bot de Yahoo para ciertas llamadas (ej. fast_info).
"""
import time
from datetime import date as date_type, datetime, timedelta, timezone

from curl_cffi import requests as curl_requests

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

USD_MXN_SYMBOL = "MXN=X"  # Yahoo: pesos por dolar

# Algunas bolsas cotizan en la subunidad de la moneda (Londres en peniques,
# Tel Aviv en agorot, Johannesburgo en centavos): sin normalizar, el precio
# saldria 100 veces mas caro. Se convierte a la moneda principal.
MINOR_UNITS = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ILA": ("ILS", 100), "ZAc": ("ZAR", 100)}


def _major_currency(currency):
    """(moneda principal, divisor) para llevar un precio a su moneda principal."""
    return MINOR_UNITS.get(currency, (currency, 1))


def _session():
    return curl_requests.Session(impersonate="chrome")


_CHART_TTL_SECONDS = 15
_chart_cache = {}  # (simbolo, rango, intervalo) -> (momento, resultado)


def _fetch_chart(symbol, range_="1mo", interval="1d"):
    # Cache corto: sin el, cada vista del portafolio vuelve a pedir a Yahoo un precio por posicion
    # y con varios usuarios a la vez Yahoo empieza a rechazar. Los resultados se leen, nunca se modifican.
    key = (symbol, range_, interval)
    hit = _chart_cache.get(key)
    if hit and time.monotonic() - hit[0] < _CHART_TTL_SECONDS:
        return hit[1]
    result = _download_chart(symbol, range_, interval)
    if len(_chart_cache) > 100:  # la busqueda es libre: que no crezca sin tope
        _chart_cache.clear()
    _chart_cache[key] = (time.monotonic(), result)
    return result


def _download_chart(symbol, range_, interval):
    response = _session().get(
        CHART_URL.format(symbol=symbol),
        params={"range": range_, "interval": interval},
        timeout=10,
    )
    response.raise_for_status()
    result = response.json().get("chart", {}).get("result")

    if not result:
        raise ValueError(f"Sin datos para el símbolo {symbol}")
    return result[0]


def get_current_price(symbol):
    result = _fetch_chart(symbol, range_="5d")
    meta = result["meta"]

    currency, divisor = _major_currency(meta.get("currency"))
    price = meta["regularMarketPrice"] / divisor
    previous_close = (meta.get("previousClose") or meta.get("chartPreviousClose")) / divisor
    change = price - previous_close
    change_percent = (change / previous_close * 100) if previous_close else 0

    return {
        "symbol": symbol,
        "price": round(price, 2),
        "previous_close": round(previous_close, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "change_period": "1d",
        "currency": currency,
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
    }


def _market_price(symbol):
    return _fetch_chart(symbol, range_="5d")["meta"]["regularMarketPrice"]


def get_fx_to_mxn(currency):
    """Pesos por unidad de `currency`, sin redondear (redondear a 2 decimales
    ya distorsiona montos grandes). Yahoo no tiene par directo contra MXN para
    todas las monedas (KRW, INR, CNY...): en ese caso se cruza via dolar."""
    if currency == "MXN":
        return 1.0
    if currency == "USD":
        return _market_price(USD_MXN_SYMBOL)
    try:
        return _market_price(f"{currency}MXN=X")
    except Exception:
        return _market_price(USD_MXN_SYMBOL) / _market_price(f"{currency}=X")


def search_symbols(query):
    """Busca acciones/ETFs disponibles en Yahoo Finance por nombre o simbolo."""
    response = _session().get(
        SEARCH_URL,
        params={"q": query, "quotesCount": 8, "newsCount": 0},
        timeout=10,
    )
    response.raise_for_status()
    quotes = response.json().get("quotes", [])

    results = []
    for quote in quotes:
        symbol = quote.get("symbol")
        if not symbol or quote.get("quoteType") not in ("EQUITY", "ETF"):
            continue
        results.append({
            "symbol": symbol,
            "name": quote.get("shortname") or quote.get("longname") or symbol,
            "exchange": quote.get("exchDisp"),
            "sector": quote.get("sectorDisp") or quote.get("typeDisp"),
        })
    return results


def _series_from_chart(result, divisor=1):
    """Serie [(fecha, precio)] ordenada y sin fechas repetidas. La fecha es la
    local de la bolsa (gmtoffset) y el precio esta ajustado por dividendos y
    splits cuando Yahoo lo trae, para que los rendimientos sean reales."""
    offset = result["meta"].get("gmtoffset", 0)
    timestamps = result.get("timestamp") or []
    indicators = result["indicators"]
    adjusted = (indicators.get("adjclose") or [{}])[0].get("adjclose")
    closes = adjusted or indicators["quote"][0].get("close", [])

    by_date = {}
    for ts, price in zip(timestamps, closes):
        if price is None:
            continue
        day = datetime.fromtimestamp(ts + offset, tz=timezone.utc).strftime("%Y-%m-%d")
        by_date[day] = price / divisor  # si Yahoo repite el dia (precio parcial), gana el ultimo
    return sorted(by_date.items())


def get_price_series(symbol, range_="5y"):
    """Historico diario para calcular riesgo, en la moneda principal de la
    accion (no en peniques). Devuelve {"series", "currency", "name", "exchange"}."""
    result = _fetch_chart(symbol, range_=range_)
    meta = result["meta"]
    currency, divisor = _major_currency(meta.get("currency"))
    return {
        "series": _series_from_chart(result, divisor),
        "currency": currency,
        "name": meta.get("shortName") or meta.get("longName") or symbol,
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
    }


def _ratio_series(numerator, denominator):
    """numerator/denominator por fecha, con el ultimo valor conocido del denominador."""
    out, j = [], -1
    for day, value in numerator:
        while j + 1 < len(denominator) and denominator[j + 1][0] <= day:
            j += 1
        if j >= 0:
            out.append((day, value / denominator[j][1]))
    return out


def get_fx_series(currency, range_="5y"):
    """Historico diario de pesos por unidad de `currency` (mismo criterio que
    get_fx_to_mxn: par directo o cruzado via dolar). None si ya es MXN."""
    if currency == "MXN":
        return None
    if currency == "USD":
        return _series_from_chart(_fetch_chart(USD_MXN_SYMBOL, range_=range_))
    try:
        return _series_from_chart(_fetch_chart(f"{currency}MXN=X", range_=range_))
    except Exception:
        usd_mxn = _series_from_chart(_fetch_chart(USD_MXN_SYMBOL, range_=range_))
        usd_per_currency = _series_from_chart(_fetch_chart(f"{currency}=X", range_=range_))
        return _ratio_series(usd_mxn, usd_per_currency)


# (dias que cubre, rango de Yahoo): se usa el primer rango que alcanza.
HISTORY_RANGES = [(31, "1mo"), (92, "3mo"), (183, "6mo"), (366, "1y"), (731, "2y")]


def get_history(symbol, days=30):
    """Cierres diarios de los ultimos `days` dias naturales (contados desde el ultimo cierre)."""
    range_ = next((r for limit, r in HISTORY_RANGES if days <= limit), "5y")
    result = _fetch_chart(symbol, range_=range_)

    timestamps = result.get("timestamp", [])
    closes = result["indicators"]["quote"][0].get("close", [])
    _, divisor = _major_currency(result["meta"].get("currency"))

    history = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        history.append({"date": date, "close": round(close / divisor, 2)})

    if not history:
        return history
    cutoff = (date_type.fromisoformat(history[-1]["date"]) - timedelta(days=days)).isoformat()
    return [point for point in history if point["date"] >= cutoff]
