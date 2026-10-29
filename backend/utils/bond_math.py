"""Matematica pura de bonos y CETES (sin I/O): precios, valor devengado, valor
de mercado y cupones. Tasas en porcentaje anual; convencion act/360 (la del
mercado de dinero mexicano).

Dos instrumentos:

- CETES (kind "cetes"): cero cupon. Se compran con descuento,
  precio = nominal / (1 + tasa * dias/360), y pagan el nominal al vencer. Si se
  mantienen, el valor sube en linea recta (interes simple) a la tasa que se
  fijo al comprarlos: ese es el valor devengado. Si se venden antes de
  vencer, se pagan a precio de mercado: el nominal descontado a la tasa de hoy
  para los dias que faltan. Si las tasas subieron desde la compra, el CETE vale
  menos que su devengado (y se puede perder); si bajaron, vale mas.

- Bono M (kind "bono_m"): tasa fija con cupon cada `coupon_days` dias (182).
  Cada subasta se modela como un bono nuevo a la par: el cupon es la tasa del
  dia de compra, y el precio inicial es el nominal. El cupon se abona al
  efectivo en cada fecha de pago y el nominal al vencer. Su precio de mercado
  es el valor presente de los cupones y el nominal que faltan a la tasa de hoy
  (precio sucio: incluye el cupon corrido), asi que sube cuando las tasas bajan
  y baja cuando suben, y mas cuanto mas largo es el plazo.

Aproximaciones conocidas: la tasa de mercado de un CETE a un plazo intermedio
se interpola entre las cuatro subastas (28/91/182/364 dias), y para el Bono M
se usa la tasa del Bono M a 10 anos para cualquier plazo restante (curva plana).
"""
from datetime import date, timedelta


def to_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def kind_of(lot):
    # Los lotes anteriores a este esquema no traen `kind`: eran CETES.
    return lot.get("kind", "cetes")


def purchase_price(lot):
    # Los lotes anteriores pagaron el nominal completo por titulo.
    return lot.get("purchase_price", lot["nominal_value"])


def cetes_price(nominal, rate_pct, term_days):
    """Precio con descuento de un CETE al plazo y tasa de rendimiento dados."""
    return round(nominal / (1 + rate_pct / 100 * term_days / 360), 6)


def new_lot(bond, quantity, name, rate_pct, purchase_date, lot_id):
    """Lote recien comprado de un bono del catalogo a la tasa de subasta."""
    purchase_date = to_date(purchase_date)
    kind = bond.get("kind", "cetes")
    lot = {
        "symbol": bond["symbol"],
        "name": name,
        "type": "bono",
        "kind": kind,
        "quantity": quantity,
        "nominal_value": bond["nominal_value"],
        "rate_at_purchase": rate_pct,
        "purchase_date": purchase_date.isoformat(),
        "maturity_date": (purchase_date + timedelta(days=bond["term_days"])).isoformat(),
        "lot_id": lot_id,
    }
    if kind == "bono_m":
        lot["purchase_price"] = bond["nominal_value"]
        lot["coupon_days"] = bond["coupon_days"]
        lot["next_coupon_date"] = (purchase_date + timedelta(days=bond["coupon_days"])).isoformat()
        lot["coupons_paid"] = 0
    else:
        lot["purchase_price"] = cetes_price(bond["nominal_value"], rate_pct, bond["term_days"])
    return lot


def cost(lot):
    """Pesos que costo el lote (lo que se pago al comprarlo)."""
    return round(purchase_price(lot) * lot["quantity"], 2)


def coupon_amount(lot):
    """Cupon por pago de todo el lote (solo Bono M)."""
    return round(
        lot["nominal_value"] * lot["quantity"] * lot["rate_at_purchase"] / 100 * lot["coupon_days"] / 360, 2
    )


def maturity_value(lot):
    """Lo que paga el lote al vencer (sin contar cupones ya abonados)."""
    if kind_of(lot) == "bono_m":
        return round(lot["nominal_value"] * lot["quantity"], 2)
    term = (to_date(lot["maturity_date"]) - to_date(lot["purchase_date"])).days
    return round(purchase_price(lot) * lot["quantity"] * (1 + lot["rate_at_purchase"] / 100 * term / 360), 2)


def accrued_value(lot, as_of):
    """Valor devengado: cuanto vale si se mantiene hasta vencer, a la tasa que se
    fijo al comprar (sube en linea recta, sin mirar el mercado)."""
    if kind_of(lot) == "bono_m":
        # Cupon corrido desde el ultimo pago; los cupones ya pagados estan en efectivo.
        last_coupon = to_date(lot["next_coupon_date"]) - timedelta(days=lot["coupon_days"])
        days = max(0, min((as_of - last_coupon).days, lot["coupon_days"]))
        return round(
            lot["nominal_value"] * lot["quantity"] * (1 + lot["rate_at_purchase"] / 100 * days / 360), 2
        )
    purchase = to_date(lot["purchase_date"])
    maturity = to_date(lot["maturity_date"])
    elapsed = max(0, min((as_of - purchase).days, (maturity - purchase).days))
    return round(
        purchase_price(lot) * lot["quantity"] * (1 + lot["rate_at_purchase"] / 100 * elapsed / 360), 2
    )


def build_curve(rates, bonds):
    """Curva de tasas de hoy a partir de {simbolo: tasa} y el catalogo de bonos."""
    return {
        "cetes": sorted(
            (b["term_days"], rates[b["symbol"]])
            for b in bonds
            if b.get("kind", "cetes") == "cetes" and b["symbol"] in rates
        ),
        "bono_m": {b["symbol"]: rates[b["symbol"]] for b in bonds if b.get("kind") == "bono_m" and b["symbol"] in rates},
    }


def cetes_yield(curve, remaining_days):
    """Tasa de mercado de un CETE al plazo restante: interpolacion lineal entre
    las subastas; fuera del rango se usa la tasa del plazo mas cercano."""
    points = curve["cetes"]
    if not points:
        raise ValueError("Sin tasas de CETES para valuar a mercado")
    if remaining_days <= points[0][0]:
        return points[0][1]
    if remaining_days >= points[-1][0]:
        return points[-1][1]
    for (t0, y0), (t1, y1) in zip(points, points[1:]):
        if t0 <= remaining_days <= t1:
            return y0 + (y1 - y0) * (remaining_days - t0) / (t1 - t0)


def market_value(lot, as_of, curve, shift=0.0):
    """Valor de mercado del lote hoy: lo que se obtendria al venderlo.
    `shift` suma puntos porcentuales a la tasa de mercado (prueba de estres)."""
    remaining = (to_date(lot["maturity_date"]) - as_of).days
    if remaining <= 0:
        return maturity_value(lot)

    if kind_of(lot) == "cetes":
        y = max(cetes_yield(curve, remaining) + shift, 0.0)
        return round(maturity_value(lot) / (1 + y / 100 * remaining / 360), 2)

    if lot["symbol"] not in curve["bono_m"]:
        raise ValueError(f"Sin tasa de mercado para {lot['symbol']}")
    y = max(curve["bono_m"][lot["symbol"]] + shift, 0.0)
    period = lot["coupon_days"]
    q = 1 + y / 100 * period / 360
    nominal = lot["nominal_value"]
    coupon = nominal * lot["rate_at_purchase"] / 100 * period / 360
    next_coupon = to_date(lot["next_coupon_date"])
    n = max(1, (to_date(lot["maturity_date"]) - next_coupon).days // period + 1)
    f = max(0, (next_coupon - as_of).days) / period

    dirty = sum((coupon + (nominal if k == n else 0)) / q ** (k - 1 + f) for k in range(1, n + 1))
    return round(dirty * lot["quantity"], 2)
