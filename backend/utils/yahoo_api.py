"""Wrapper sobre la API de graficas de Yahoo Finance para precios e historicos.

Se llama directo al endpoint de graficas (chart) con curl_cffi impersonando
un navegador real, en vez de usar yfinance: la libreria yfinance no siempre
respeta la sesion personalizada que se le pasa, lo que termina disparando
el bloqueo anti-bot de Yahoo para ciertas llamadas (ej. fast_info).
"""
from datetime import datetime, timezone

from curl_cffi import requests as curl_requests

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"


def _session():
    return curl_requests.Session(impersonate="chrome")


def _fetch_chart(symbol, range_="1mo", interval="1d"):
    response = _session().get(
        CHART_URL.format(symbol=symbol),
        params={"range": range_, "interval": interval},
        timeout=10,
    )
    response.raise_for_status()
    result = response.json().get("chart", {}).get("result")

    if not result:
        raise ValueError(f"Sin datos para el simbolo {symbol}")
    return result[0]


def get_current_price(symbol):
    result = _fetch_chart(symbol, range_="5d")
    meta = result["meta"]

    price = meta["regularMarketPrice"]
    previous_close = meta.get("previousClose") or meta.get("chartPreviousClose")
    change = price - previous_close
    change_percent = (change / previous_close * 100) if previous_close else 0

    return {
        "symbol": symbol,
        "price": round(price, 2),
        "previous_close": round(previous_close, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "change_period": "1d",
    }


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


def get_history(symbol, days=30):
    range_ = "3mo" if days > 30 else "1mo"
    result = _fetch_chart(symbol, range_=range_)

    timestamps = result.get("timestamp", [])
    closes = result["indicators"]["quote"][0].get("close", [])

    history = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        history.append({"date": date, "close": round(close, 2)})

    return history[-days:]
