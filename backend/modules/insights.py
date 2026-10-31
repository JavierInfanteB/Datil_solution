"""Ganancias y perdidas, activos en tendencia y movimiento mensual/anual de las acciones de un grupo de clientes.

Lo usan el consultor (sus clientes) y el admin (todos). Solo lee: carteras sin cobrar cupones ni ejecutar ordenes.
"""
from collections import defaultdict
from datetime import date, timedelta

from modules.portfolio import build_portfolio_view
from utils.data_store import read_json
from utils.market_data import get_history

TOP = 8
MONTHS = 6  # meses de variacion mes a mes
YEAR_DAYS = 365
HISTORY_DAYS = 400


def _pct(new, old):
    return round((new / old - 1) * 100, 2) if old else None


def movements(held):
    """Variacion mensual (ultimos MONTHS meses) y anual de cada accion. `held`: {simbolo: {name, holders}}."""
    labels = None
    rows = []
    for symbol, info in held.items():
        try:
            closes = get_history(symbol, "accion", days=HISTORY_DAYS)
        except Exception:
            continue  # sin historico de Yahoo para ese simbolo
        if len(closes) < 2:
            continue
        month_end = {}
        for point in closes:  # cierres en orden: el ultimo de cada mes se queda
            month_end[point["date"][:7]] = point["close"]
        months = list(month_end)
        labels = labels or months[-MONTHS:]
        monthly = [_pct(month_end[m], month_end[months[i - 1]]) if m in month_end and i > 0 else None
                   for i, m in enumerate(months)][-MONTHS:]
        last = closes[-1]
        cutoff = (date.fromisoformat(last["date"]) - timedelta(days=YEAR_DAYS)).isoformat()
        base = next((p for p in closes if p["date"] >= cutoff), None)
        year = _pct(last["close"], base["close"]) if base and base["date"] <= (
            date.fromisoformat(cutoff) + timedelta(days=7)).isoformat() else None
        rows.append({"symbol": symbol, "name": info["name"], "holders": info["holders"], "monthly": monthly, "year_pct": year})
    return {"months": labels or [], "rows": rows}


def build_insights(clients, days=30):
    """`clients`: usuarios (dicts con username y name). `days`: ventana de las tendencias."""
    first_day = (date.today() - timedelta(days=days - 1)).isoformat()
    all_transactions = read_json("transactions.json")

    pnl, trending, held, monthly_realized = [], {}, {}, defaultdict(float)
    for client in clients:
        username = client["username"]
        view = build_portfolio_view(username, settle=False)
        transactions = all_transactions.get(username, [])
        unrealized = sum(h["gain_mxn"] for h in view["holdings"] if h.get("gain_mxn") is not None)
        sold = [t for t in transactions if t.get("realized_pnl_mxn") is not None]
        realized = sum(t["realized_pnl_mxn"] for t in sold)
        for t in sold:
            monthly_realized[t["date"][:7]] += t["realized_pnl_mxn"]
        pnl.append({"username": username, "client": client["name"], "unrealized": round(unrealized, 2),
                    "realized": round(realized, 2), "total": round(unrealized + realized, 2)})

        for h in view["holdings"]:
            if h["type"] == "accion":
                held.setdefault(h["symbol"], {"name": h["name"], "holders": 0})["holders"] += 1
        for t in transactions:
            if t["side"] in ("buy", "sell") and t["date"][:10] >= first_day:
                row = trending.setdefault((t["type"], t["symbol"]), {
                    "type": t["type"], "symbol": t["symbol"], "name": t["name"],
                    "buyers": set(), "sellers": set(), "volume_mxn": 0})
                row["buyers" if t["side"] == "buy" else "sellers"].add(username)
                row["volume_mxn"] += t["total_mxn"]
                if t["type"] == "accion":
                    held.setdefault(t["symbol"], {"name": t["name"], "holders": 0})

    ranked = sorted(trending.values(), key=lambda r: (-len(r["buyers"]), -r["volume_mxn"]))[:TOP]
    return {
        "days": days,
        "pnl": {
            "clients": sorted(pnl, key=lambda r: -r["total"]),
            "totals": {k: round(sum(r[k] for r in pnl), 2) for k in ("unrealized", "realized", "total")},
            "realized_by_month": [{"month": m, "realized": round(v, 2)} for m, v in sorted(monthly_realized.items())[-12:]],
        },
        "trending": [{**r, "buyers": len(r["buyers"]), "sellers": len(r["sellers"]), "volume_mxn": round(r["volume_mxn"], 2)}
                     for r in ranked],
        "movements": movements(held),
    }
