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
  Cada compra se simula como un bono nuevo a la par: el cupon es la tasa del dia de compra y el precio inicial es el
  nominal (simulacion: el cupon real de cada emision viene en la convocatoria). El cupon se abona al efectivo en cada
  fecha de pago (si cae en dia inhabil, el habil anterior) por los dias reales del periodo, y el nominal al vencer. Su
  precio de mercado es el sucio con la formula de Banxico: valor presente de los cupones y el nominal que faltan al
  rendimiento de mercado del plazo restante, asi que sube cuando las tasas bajan y baja cuando suben.

Mercado de cada dia: el vector de precios "on the run" de Banxico (utils/market_vector.py). De los CETES se toma su
rendimiento y plazo por vencer; de los Bonos M, el rendimiento que da su precio limpio (bono_yield_from_clean_price), y
los lotes se valuan a la tasa interpolada en su plazo restante. Estas cuentas reproducen los precios publicados.
shortcut: la formula de Bono M (bono_clean_price) supone periodos de 182 dias, como la formula reducida de Banxico; los
periodos reales con dias inhabiles difieren por unos dias. Revisar si se necesita el calendario exacto de cada emision.
"""
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from utils import calendar_mx, market_vector

# Subastas: Banxico coloca (liquida) los jueves y subasta dos dias habiles antes; ver utils/calendar_mx.py.
# Reglas de operacion de cetesdirecto que se simulan:
MIN_INVESTMENT = 100  # pesos minimos por compra; se compra por monto y lo que no alcanza para un titulo queda en efectivo
LOCK_BUSINESS_DAYS = 3  # vender o cambiar la reinversion: hasta 3 dias habiles antes del vencimiento
REINVEST_SYMBOL = "CETES28"  # la reinversion automatica al vencimiento va a CETES a 28 dias
REINVEST_MIN_TITLES = 10  # si alcanza para al menos 10 titulos; si no, el dinero queda en efectivo


def to_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def business_days_before(day, n):
    """El dia que queda `n` dias habiles antes de `day` (no cuenta fines de semana ni inhabiles bancarios)."""
    return calendar_mx.business_days_before(to_date(day), n)


def last_change_day(lot):
    """Ultimo dia para vender el lote antes de que venza o para cambiar su reinversion."""
    return business_days_before(lot["maturity_date"], LOCK_BUSINESS_DAYS)


def kind_of(lot):
    # Los lotes anteriores a este esquema no traen `kind`: eran CETES.
    return lot.get("kind", "cetes")


def purchase_price(lot):
    # Los lotes anteriores pagaron el nominal completo por titulo.
    return lot.get("purchase_price", lot["nominal_value"])


def cetes_price(nominal, rate_pct, term_days):
    """Precio con descuento de un CETE: VN / (1 + r*t/360), a 7 decimales como lo calcula Banxico."""
    price = Decimal(str(nominal)) / (1 + Decimal(str(rate_pct)) / 100 * term_days / 360)
    return float(price.quantize(Decimal("1e-7"), ROUND_HALF_UP))


def titles_for_amount(amount_mxn, unit_price):
    """Titulos enteros que alcanzan para un monto: el monto entre el precio de cada uno, truncado, como asigna Banxico.
    El importe se liquida en centavos, asi que un titulo mas alcanza si su costo redondeado a centavos no pasa del monto
    (un monto que sale de un costo ya redondeado, como el de una reinversion, no pierde un titulo por medio centavo)."""
    amount, price = Decimal(str(amount_mxn)), Decimal(str(unit_price))
    titles = int((amount / price).to_integral_value(ROUND_DOWN))
    while (price * (titles + 1)).quantize(Decimal("0.01"), ROUND_HALF_UP) <= amount:
        titles += 1
    return titles


def new_lot(bond, quantity, name, rate_pct, purchase_date, lot_id, term_days=None):
    """Lote recien comprado de un bono del catalogo a la tasa de subasta. `term_days` es el plazo real de esa
    emision (Banxico lo publica por subasta: un CETE de 182 dias puede salir a 175) y ya trae su vencimiento; con el
    plazo nominal del catalogo, un vencimiento inhabil se paga el dia habil inmediato anterior."""
    purchase_date = to_date(purchase_date)
    maturity = purchase_date + timedelta(days=term_days or bond["term_days"])
    if not term_days:
        maturity = calendar_mx.previous_business_day(maturity)
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
        "maturity_date": maturity.isoformat(),
        "lot_id": lot_id,
    }
    if kind == "bono_m":
        lot["purchase_price"] = bond["nominal_value"]
        lot["coupon_days"] = bond["coupon_days"]
        lot["coupons_paid"] = 0
        lot["next_coupon_date"] = coupon_schedule(lot)[0].isoformat()
    else:
        lot["purchase_price"] = cetes_price(bond["nominal_value"], rate_pct, (maturity - purchase_date).days)
    return lot


def coupon_schedule(lot):
    """Fechas de pago de cupon de un Bono M, de la primera al vencimiento. Cada pago cae a `coupon_days` de la compra y,
    si ese dia es inhabil, se corre al dia habil inmediato anterior; el ultimo pago es el vencimiento."""
    start, maturity, period = to_date(lot["purchase_date"]), to_date(lot["maturity_date"]), lot["coupon_days"]
    dates, k = [], 1
    while True:
        pay = calendar_mx.previous_business_day(start + timedelta(days=k * period))
        if pay >= maturity:
            return dates + [maturity]
        dates.append(pay)
        k += 1


def _coupon_periods(lot):
    """(inicio, pago) de cada periodo de cupon; los intereses corren por los dias reales entre fechas de pago."""
    previous, periods = to_date(lot["purchase_date"]), []
    for pay in coupon_schedule(lot):
        periods.append((previous, pay))
        previous = pay
    return periods


def cost(lot):
    """Pesos que costo el lote (lo que se pago al comprarlo)."""
    return round(purchase_price(lot) * lot["quantity"], 2)


def coupon_amount(lot, number=None):
    """Cupon del periodo `number` (1 es el primero; por defecto el siguiente por pagar) de todo el lote (solo Bono M):
    valor nominal x dias reales del periodo x tasa / 360."""
    periods = _coupon_periods(lot)
    start, pay = periods[min(number or lot.get("coupons_paid", 0) + 1, len(periods)) - 1]
    rate = lot.get("coupon_rate", lot["rate_at_purchase"])
    return round(lot["nominal_value"] * lot["quantity"] * rate / 100 * (pay - start).days / 360, 2)


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
        periods = _coupon_periods(lot)
        start, pay = periods[min(lot.get("coupons_paid", 0), len(periods) - 1)]
        days = max(0, min((as_of - start).days, (pay - start).days))
        rate = lot.get("coupon_rate", lot["rate_at_purchase"])
        return round(lot["nominal_value"] * lot["quantity"] * (1 + rate / 100 * days / 360), 2)
    purchase = to_date(lot["purchase_date"])
    maturity = to_date(lot["maturity_date"])
    elapsed = max(0, min((as_of - purchase).days, (maturity - purchase).days))
    return round(
        purchase_price(lot) * lot["quantity"] * (1 + lot["rate_at_purchase"] / 100 * elapsed / 360), 2
    )


def build_curve(rates, bonds):
    """Curva de tasas a partir de {simbolo: tasa} y el catalogo de bonos (tasas de la ultima subasta de cada uno).
    La curva de mercado de cada dia sale del vector de precios de Banxico: ver utils/market_data.get_bond_curve."""
    return {
        "cetes": sorted(
            (b["term_days"], rates[b["symbol"]])
            for b in bonds
            if b.get("kind", "cetes") == "cetes" and b["symbol"] in rates
        ),
        "bono_m": {b["symbol"]: rates[b["symbol"]] for b in bonds if b.get("kind") == "bono_m" and b["symbol"] in rates},
    }


def curve_from_vector(values):
    """Curva de mercado del dia a partir de {serie: valor} del vector de Banxico: los CETES con su rendimiento y su plazo
    por vencer, y los Bonos M con el rendimiento que da su precio limpio (los rangos que hoy no cotizan se omiten)."""
    cetes = sorted((values[term], values[rate]) for term, rate in market_vector.CETES if term in values and rate in values)
    bonos = sorted(
        (values[term], bono_yield_from_clean_price(values[price], values[coupon], int(values[term])))
        for term, price, coupon in market_vector.BONOS_M if term in values and price in values and coupon in values
    )
    if not cetes:
        raise ValueError("Sin tasas de CETES para valuar a mercado")
    return {"cetes": cetes, "bono_m": {}, "bono_m_curve": bonos}


def interpolate(points, x):
    """Interpolacion lineal entre nodos (x, y) ordenados; fuera del rango se usa el nodo mas cercano."""
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def cetes_yield(curve, remaining_days):
    """Tasa de mercado de un CETE al plazo restante: interpolacion lineal entre los CETES 'on the run' del dia."""
    if not curve["cetes"]:
        raise ValueError("Sin tasas de CETES para valuar a mercado")
    return interpolate(curve["cetes"], remaining_days)


def bono_m_yield(curve, lot, remaining_days):
    """Rendimiento de mercado de un Bono M al plazo restante: de la curva del dia si la hay, o la tasa de su subasta."""
    if curve.get("bono_m_curve"):
        return interpolate(curve["bono_m_curve"], remaining_days)
    if lot["symbol"] not in curve["bono_m"]:
        raise ValueError(f"Sin tasa de mercado para {lot['symbol']}")
    return curve["bono_m"][lot["symbol"]]


def bono_clean_price(coupon_pct, yield_pct, days_to_maturity, nominal=100, period=182):
    """Precio limpio de un Bono M por titulo, con la formula de Banxico (cupones iguales de `period` dias, un solo
    rendimiento). Sirve para cotizar con el vector de precios y para sacar el rendimiento de un precio."""
    k = -(-days_to_maturity // period)  # cupones por pagar, incluyendo el vigente
    to_next = days_to_maturity - (k - 1) * period
    coupon = nominal * coupon_pct / 100 * period / 360
    r = yield_pct / 100 * period / 360
    exponent = to_next / period
    dirty = sum(coupon / (1 + r) ** (j - 1 + exponent) for j in range(1, k + 1)) + nominal / (1 + r) ** (k - 1 + exponent)
    return dirty - coupon * (period - to_next) / period


def bono_accrued(coupon_pct, days_to_maturity, nominal=100, period=182):
    """Intereses devengados del cupon vigente por titulo (la diferencia entre precio sucio y limpio)."""
    to_next = days_to_maturity - (-(-days_to_maturity // period) - 1) * period
    return nominal * coupon_pct / 100 * (period - to_next) / 360


def bono_yield_from_clean_price(clean_price, coupon_pct, days_to_maturity, nominal=100, period=182):
    """Rendimiento anual (%) que da un precio limpio de Bono M; el precio baja cuando sube el rendimiento (biseccion)."""
    low, high = 0.0, 100.0
    for _ in range(200):
        mid = (low + high) / 2
        if bono_clean_price(coupon_pct, mid, days_to_maturity, nominal, period) > clean_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def market_value(lot, as_of, curve, shift=0.0):
    """Valor de mercado del lote hoy: lo que se obtendria al venderlo.
    `shift` suma puntos porcentuales a la tasa de mercado (prueba de estres)."""
    remaining = (to_date(lot["maturity_date"]) - as_of).days
    if remaining <= 0:
        return maturity_value(lot)

    if kind_of(lot) == "cetes":
        y = max(cetes_yield(curve, remaining) + shift, 0.0)
        return round(maturity_value(lot) / (1 + y / 100 * remaining / 360), 2)

    # Bono M, formula general de Banxico: cada cupon y el principal se descuentan con (1 + r*Nj/360)^-(j - d/N1), donde
    # Nj son los dias reales de cada periodo, d los dias corridos del vigente y j cuenta los pagos por recibir.
    y = max(bono_m_yield(curve, lot, remaining) + shift, 0.0) / 100
    periods = _coupon_periods(lot)
    paid = min(lot.get("coupons_paid", 0), len(periods) - 1)
    first_start = periods[paid][0]
    n1 = (periods[paid][1] - first_start).days
    elapsed = max(0, min((as_of - first_start).days, n1))
    nominal, rate = lot["nominal_value"], lot.get("coupon_rate", lot["rate_at_purchase"]) / 100
    dirty = 0.0
    for j, (start, pay) in enumerate(periods[paid:], 1):
        days = (pay - start).days
        flow = nominal * rate * days / 360 + (nominal if j == len(periods) - paid else 0)
        dirty += flow / (1 + y * days / 360) ** (j - elapsed / n1)
    return round(dirty * lot["quantity"], 2)
