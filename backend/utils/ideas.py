"""Ideas de acciones para que el consultor las revise con sus clientes (sin I/O salvo la lista de seguimiento).

Es un filtro con datos del pasado, no una prediccion: solo entran acciones de riesgo bajo (el mismo puntaje que ve
el cliente) y que ademas estan cerca de su minimo de los ultimos anos o traen buena tendencia. Nada de esto dice que
vayan a subir.
"""
NEAR_LOW = 15  # % sobre el minimo del historico para decir que esta cerca de el
WATCHLIST = (
    "KO", "PEP", "PG", "JNJ", "WMT", "COST", "MCD", "VZ", "T", "MRK", "ABBV", "PFE", "XOM", "CVX", "BRK-B",
    "V", "MA", "UNH", "HD", "LLY", "SPY", "VOO", "VTI", "ACWI", "EFA", "QQQ", "VNQ", "GLD",
)


def facts(series):
    """series: [(fecha, precio)] del mas viejo al mas nuevo."""
    prices = [p for _, p in series]
    last = prices[-1]
    recent = prices[-200:]
    six = prices[-126] if len(prices) > 126 else None
    return {
        "price": round(last, 2),
        "above_low_pct": round((last / min(prices) - 1) * 100, 1),
        "below_high_pct": round((last / max(prices) - 1) * 100, 1),
        "change_6m_pct": round((last / six - 1) * 100, 1) if six else None,
        "above_ma200": len(recent) >= 200 and last > sum(recent) / len(recent),
        "years": round(len(prices) / 252, 1),
    }


def reasons(f):
    found = []
    if f["above_low_pct"] <= NEAR_LOW:
        found.append(f"Cerca de su mínimo de {f['years']} años (+{f['above_low_pct']}%)")
    if f["above_ma200"] and (f["change_6m_pct"] or 0) > 0:
        found.append(f"Buena tendencia: +{f['change_6m_pct']}% en 6 meses y sobre su promedio de 200 días")
    return found
