"""Sugerencias para bajar el riesgo de un cliente (sin I/O).

Solo hablan de riesgo: ninguna dice que comprar para ganar mas. Reciben lo que devuelve
modules/risk.portfolio_risk_for y cada una trae lo que habria que mover y cuanto aliviaria
en el escenario correspondiente, para que el consultor decida con numeros.
"""

MAX_POSITION = 35  # % del portafolio en una sola accion antes de sugerir reducirla
TARGET_POSITION = 25  # % al que se sugiere dejarla
HIGH_RISK_WEIGHT = 10  # % minimo de una accion de riesgo alto para avisar
MIN_CASH = 5  # % de efectivo por debajo del cual falta colchon
MAX_FOREIGN = 70  # % en moneda extranjera
BAD_SCENARIO = 15  # % de perdida en algun escenario que ya es motivo de aviso
MIN_STOCKS = 3  # menos acciones que estas, con casi todo en acciones, es poca diversificacion
WORSE_THAN_MARKET = 1.25  # veces la caida maxima del mercado global

SEVERITY_ORDER = {"alta": 0, "media": 1, "baja": 2}


def _mxn(value):
    return f"{'-' if value < 0 else ''}${abs(value):,.0f}"


def suggestions(risk):
    """Lista de {id, severity, title, detail, ...} ordenada de mas a menos grave."""
    found = []

    def add(id, severity, title, detail, **extra):
        found.append({"id": id, "severity": severity, "title": title, "detail": detail, **extra})

    total, stocks = risk["total"], risk["stocks"]

    for p in stocks["positions"]:
        if p["weight"] > MAX_POSITION:
            sell = (p["weight"] - TARGET_POSITION) / 100 * total
            add("concentration", "alta" if p["weight"] > 50 else "media",
                f"Reducir {p['symbol']}: pesa {p['weight']}% del portafolio",
                f"Llevarla a {TARGET_POSITION}% implica vender unos {_mxn(sell)}. Si las acciones cayeran 20%, "
                f"se perderían unos {_mxn(0.2 * sell)} menos.",
                symbol=p["symbol"], amount_mxn=round(sell, 2))
        if p.get("level") == "alto" and p["weight"] >= HIGH_RISK_WEIGHT:
            add("risky_stock", "alta" if p["weight"] >= 20 else "media",
                f"{p['symbol']} tiene riesgo alto y pesa {p['weight']}%",
                f"Puntaje {p['score']} de 100. Conviene reducirla o acotar cuánto del portafolio puede llegar a pesar.",
                symbol=p["symbol"])

    scenarios = [s for s in risk["scenarios"] if s["impact_percent"] is not None]
    worst = min(scenarios, key=lambda s: s["impact_percent"], default=None)
    if worst and worst["impact_percent"] <= -BAD_SCENARIO:
        add("scenario", "alta" if worst["impact_percent"] <= -25 else "media",
            f"Un escenario adverso costaría {abs(worst['impact_percent'])}% del portafolio",
            f"{worst['label']}: {_mxn(worst['impact_mxn'])}.")

    exposure = risk["concentration"]["currency_exposure"]
    foreign = sum(share for currency, share in exposure.items() if currency != "MXN")
    if foreign > MAX_FOREIGN:
        add("currency", "media", f"{round(foreign)}% del portafolio está en moneda extranjera",
            "Si el peso se aprecia, el valor en pesos baja aunque las acciones no se muevan.")

    if 0 < len(stocks["positions"]) < MIN_STOCKS and stocks["share"] >= 50:
        add("diversification", "media", f"Solo {len(stocks['positions'])} acción(es) con {stocks['share']}% en acciones",
            "Poca diversificación: un mal resultado de una sola empresa pega fuerte.")

    history = risk["history"]
    if history and "error" not in history and history["max_drawdown"] > history["benchmark"]["max_drawdown"] * WORSE_THAN_MARKET:
        add("worse_than_market", "media",
            f"Ha caído más que el mercado global: {history['max_drawdown']}% contra {history['benchmark']['max_drawdown']}%",
            "Con la mezcla de hoy, su peor caída histórica supera a la de un fondo de acciones de todo el mundo.")

    cash_share = risk["concentration"]["cash_share"]
    if cash_share < MIN_CASH and stocks["share"] > 60:
        add("liquidity", "baja", f"Solo {cash_share}% en efectivo",
            "Sin colchón, ante un retiro o una caída habría que vender acciones a mal precio.")

    if risk["incomplete"]:
        add("incomplete", "baja", "No se pudo valuar alguna posición",
            "Las cifras de riesgo no la incluyen y pueden estar subestimadas.")

    return sorted(found, key=lambda s: SEVERITY_ORDER[s["severity"]])
