"""Punto unico de acceso a precios/tasas actuales e historicos.

Los modulos de negocio (dashboard, portfolio, trading, history) solo hablan
con este archivo. Las acciones aceptan cualquier simbolo valido de Yahoo
Finance (no hay catalogo fijo); los bonos si estan restringidos al catalogo
curado de series de Banxico (tablas instrumentos y series_mercado), porque cada uno requiere un
series_id especifico que no se puede "buscar" igual que un ticker.
"""

import time
from datetime import date

from db import portfolio as pf_repo
from utils import banxico_api, bond_math, calendar_mx, market_vector, yahoo_api


def _find_bond(symbol):
    bonds = {b["symbol"]: b for b in list_bonds()}
    if symbol not in bonds:
        raise ValueError(f"Bono desconocido: {symbol}")
    return bonds[symbol]


def get_current_price(symbol, asset_type="accion"):
    if asset_type == "bono":
        asset = _find_bond(symbol)
        return banxico_api.get_bond_rate(asset["series_id"], symbol)
    return yahoo_api.get_current_price(symbol)


def get_history(symbol, asset_type="accion", days=30):
    if asset_type == "bono":
        asset = _find_bond(symbol)
        return banxico_api.get_bond_history(asset["series_id"], days=max(days, 180))
    return yahoo_api.get_history(symbol, days=days)


def get_fx_to_mxn(currency):
    """Pesos por unidad de la moneda de cotizacion de una accion."""
    return yahoo_api.get_fx_to_mxn(currency)


def search_stocks(query):
    return yahoo_api.search_symbols(query)


def list_bonds():
    return pf_repo.catalog_bonds()


_CURVE_TTL_SECONDS = 30 * 60
_curve_cache = []  # [(momento, curva)]


def get_udi(day):
    """Valor de la UDI en pesos del dia `day`. Banxico la publica todos los dias, tambien sabados y domingos."""
    return banxico_api.get_rate_on(market_vector.UDI, day)


def get_bond_curve():
    """Curva de mercado de hoy para valuar los lotes: el vector de precios 'on the run' de Banxico (mercado secundario de
    cada dia, no las tasas de la ultima subasta). Ver bond_math.curve_from_vector y utils/market_vector.py."""
    if _curve_cache and time.monotonic() - _curve_cache[0][0] < _CURVE_TTL_SECONDS:
        return _curve_cache[0][1]
    ids, values = market_vector.all_series(), {}
    for i in range(0, len(ids), 10):  # pocas series por consulta; cada grupo tiene su cache de 30 minutos
        values.update(banxico_api.get_latest_rates(ids[i:i + 10]))
    try:  # el precio de los Udibonos va en pesos: se pasa a UDIS con la UDI del dia del vector
        vector_day = date.fromisoformat(banxico_api.get_latest_dated(market_vector.CETES[0][1])[1])
        vector_udi, udi = get_udi(vector_day), get_udi(date.today())
    except Exception:
        vector_udi = udi = None  # sin UDI los Udibonos se valuan devengados
    curve = bond_math.curve_from_vector(values, vector_udi, udi)
    _curve_cache[:] = [(time.monotonic(), curve)]
    return curve


def get_bpa_start_rate(bond, start):
    """Tasa del cupon de un BPA que empieza en la colocacion `start`: la mayor entre los CETES del plazo del cupon en esa
    fecha y la TPFG del dia de la subasta (BPAG28 y BPAG91), o solo los CETES a 182 dias (BPA182, que ademas compara la UDI
    al final del periodo). ValueError si Banxico aun no publica esas tasas."""
    cetes = banxico_api.get_rate_on(bond["cetes_series_id"], start)
    tpfg = banxico_api.get_rate_on(bond["tpfg_series_id"], calendar_mx.auction_date(start)) if bond.get("tpfg_series_id") else None
    return bond_math.bpa_rate(cetes, tpfg)


def get_bond_price_on(bond, placement):
    """Precio limpio por titulo de un bono de tasa variable en la colocacion `placement` (vector on the run de Banxico)."""
    return banxico_api.get_rate_on(bond["price_series_id"], placement)


def get_bond_auction_rate(symbol, auction_date):
    """Tasa de la subasta de Banxico del dia `auction_date`. Banxico la etiqueta con la fecha de colocacion (el jueves o
    el dia habil que lo sustituye). ValueError si ese dia no hubo subasta o aun no se publica."""
    placement = calendar_mx.placement_of_auction(auction_date)
    return banxico_api.get_rate_on(_find_bond(symbol)["series_id"], placement)


def get_bond_auction_term(symbol, auction_date):
    """Plazo real en dias de lo colocado en la subasta (serie `term_series_id` del catalogo). ValueError si no hay."""
    series_id = _find_bond(symbol).get("term_series_id")
    if not series_id:
        raise ValueError(f"{symbol} no tiene serie de plazo")
    term = int(round(banxico_api.get_rate_on(series_id, calendar_mx.placement_of_auction(auction_date))))
    if term <= 0:
        raise ValueError(f"Plazo invalido para {symbol}: {term}")
    return term
