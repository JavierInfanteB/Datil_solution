"""Reporte de un cliente por mes, trimestre o ano en curso (sin I/O): que logro, ingresos y que puede mejorar."""
from datetime import date, timedelta

PERIODS = ("month", "quarter", "year")
LABEL = {"month": "este mes", "quarter": "este trimestre", "year": "este año"}


def _mxn(value):
    return f"{'-' if value < 0 else ''}${abs(value):,.0f}"


def period_start(period, today):
    if period == "month":
        return today.replace(day=1)
    if period == "quarter":
        return today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1)
    return today.replace(month=1, day=1)


def _bucket_of(period, day):
    """Barra de la grafica: la semana (su lunes) dentro del mes; el mes dentro del trimestre y del ano."""
    if period == "month":
        return (day - timedelta(days=day.weekday())).isoformat()[5:]
    return day.isoformat()[:7]


def _buckets(period, start, today):
    labels, day = [], start
    while day <= today:
        label = _bucket_of(period, day)
        if label not in labels:
            labels.append(label)
        day += timedelta(days=1)
    return labels


def _sale(t):
    return {"symbol": t["symbol"], "date": t["date"][:10], "realized_pnl_mxn": t["realized_pnl_mxn"]}


def build(period, transactions, view, goals, suggestions, today):
    start = period_start(period, today)
    mine = [t for t in transactions if t["date"][:10] >= start.isoformat()]
    series = {label: {"label": label, "realized": 0.0, "income": 0.0} for label in _buckets(period, start, today)}
    sales = []
    for t in mine:
        row = series[_bucket_of(period, min(date.fromisoformat(t["date"][:10]), today))]  # las fechas vienen en UTC y pueden ir un dia adelante
        if t.get("realized_pnl_mxn") is not None:
            row["realized"] += t["realized_pnl_mxn"]
            sales.append(t)
        if t["side"] == "coupon":
            row["income"] += t["total_mxn"]

    realized = sum(t["realized_pnl_mxn"] for t in sales)
    income = sum(t["total_mxn"] for t in mine if t["side"] == "coupon")
    trades = [t for t in mine if t["side"] in ("buy", "sell")]
    unrealized = sum(h["gain_mxn"] for h in view["holdings"] if h.get("gain_mxn") is not None)
    won, lost = [t for t in sales if t["realized_pnl_mxn"] > 0], [t for t in sales if t["realized_pnl_mxn"] < 0]
    goal_rows = [{**g, "progress_pct": round(view["portfolio_total"] / g["target_mxn"] * 100, 1)} for g in goals]

    achievements = []
    if won:
        achievements.append(f"{len(won)} venta(s) con ganancia: {_mxn(sum(t['realized_pnl_mxn'] for t in won))} realizados.")
    if income:
        achievements.append(f"Cobró {_mxn(income)} en cupones de bonos.")
    achievements += [f"Meta «{g['title']}» alcanzada." for g in goal_rows if g["progress_pct"] >= 100]
    if not achievements:
        achievements.append(f"Todavía no hay resultados realizados {LABEL[period]}.")

    improvements = [s["title"] for s in suggestions[:3]]
    if lost:
        improvements.append(f"{len(lost)} venta(s) con pérdida ({_mxn(sum(t['realized_pnl_mxn'] for t in lost))}): revisar qué pasó.")
    if not goals:
        improvements.append("Todavía no hay metas: ponerlas ayuda a medir el avance.")

    best = max(sales, key=lambda t: t["realized_pnl_mxn"], default=None)
    worst = min(sales, key=lambda t: t["realized_pnl_mxn"], default=None)
    return {
        "period": period, "start": start.isoformat(), "end": today.isoformat(),
        "realized": round(realized, 2), "income": round(income, 2), "unrealized": round(unrealized, 2),
        "portfolio_total": view["portfolio_total"],
        "trades": {"count": len(trades), "volume_mxn": round(sum(t["total_mxn"] for t in trades), 2)},
        "series": [{**r, "realized": round(r["realized"], 2), "income": round(r["income"], 2)} for r in series.values()],
        "best_sale": best and _sale(best), "worst_sale": worst and _sale(worst),
        "goals": goal_rows, "achievements": achievements, "improvements": improvements,
    }
