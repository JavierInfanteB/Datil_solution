"""Contexto de riesgo de cada compra y venta de acciones (sin I/O).

Para cada operacion mira el precio en pesos de ese dia: que tan riesgosa era la accion con lo que
se sabia entonces (el mismo puntaje de risk_engine, calculado solo con datos hasta esa fecha), a
cuanto estaba de su maximo de 52 semanas y que hizo el precio despues. Tambien cuanto tiempo se
tuvo lo que se vendio. Es contexto para el consultor, no un veredicto de si la operacion fue buena.
"""
from bisect import bisect_right
from datetime import date

from utils import risk_engine

NEAR_PEAK = 3  # % bajo el maximo de 52 semanas: "cerca de su maximo"
FALLING = 20  # % bajo el maximo de 52 semanas: "en plena caida"


def _upto(series, day):
    """Prefijo de una serie [(fecha, precio)] con fechas <= day."""
    return series[: bisect_right([d for d, _ in series], day)]


def _flags(timing, side):
    flags = []
    if timing["risk"] and timing["risk"]["level"] == "alto":
        flags.append("Acción de riesgo alto ese día")
    if side == "buy" and timing["from_peak_pct"] <= NEAR_PEAK:
        flags.append("Compra cerca de su máximo de 52 semanas")
    if timing["from_peak_pct"] >= FALLING:
        flags.append("Compra en plena caída" if side == "buy" else "Venta tras una caída fuerte")
    return flags


def analyze(series_mxn, series_native, bench_native, day, side):
    """Contexto de una operacion hecha el `day` (YYYY-MM-DD); side: buy | sell.
    None si la fecha es anterior a la historia disponible."""
    past = _upto(series_mxn, day)
    if not past:
        return None

    prices = [p for _, p in series_mxn]
    i = len(past) - 1
    price = prices[i]
    window = prices[max(0, i - risk_engine.TRADING_DAYS + 1): i + 1]
    timing = {
        "price_date": past[-1][0],
        "from_peak_pct": round((1 - price / max(window)) * 100, 1),
        # Lo que hizo el precio en pesos desde esa fecha hasta hoy: lo peor que vivio y como va.
        "after": {
            "worst_pct": round((min(prices[i:]) / price - 1) * 100, 1),
            "now_pct": round((prices[-1] / price - 1) * 100, 1),
        },
        "risk": None,
    }
    try:
        metrics = risk_engine.compute_metrics(past, _upto(series_native, day), _upto(bench_native, day))
        scored = risk_engine.score_metrics(metrics)
        timing["risk"] = {"score": scored["score"], "level": scored["level"]}
    except ValueError:
        pass  # menos de ~1 ano de historia antes de esa fecha: no hay puntaje que calcular
    timing["flags"] = _flags(timing, side)
    return timing


def holding_days(transactions):
    """{id de venta: dias promedio que se tuvo lo vendido}, casando ventas con compras en orden
    (la compra mas vieja sale primero). Lo vendido de posiciones sin compra registrada no cuenta,
    y si nada casa no hay dato."""
    lots, result = {}, {}
    for t in sorted(transactions, key=lambda t: t["date"]):
        if t.get("type") != "accion":
            continue
        queue = lots.setdefault(t["symbol"], [])
        day = date.fromisoformat(t["date"][:10])
        if t["side"] == "buy":
            queue.append([day, t["quantity"]])
            continue

        remaining, matched, weighted = t["quantity"], 0.0, 0.0
        while remaining > 1e-9 and queue:
            bought_on, quantity = queue[0]
            take = min(quantity, remaining)
            weighted += take * (day - bought_on).days
            matched += take
            remaining -= take
            queue[0][1] -= take
            if queue[0][1] <= 1e-9:
                queue.pop(0)
        if matched:
            result[t["id"]] = round(weighted / matched)
    return result
