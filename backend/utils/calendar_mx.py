"""Calendario bancario de Mexico y fechas de subasta de Banxico (sin I/O).

Reglas de Banxico (capitulo II de "Mercado de valores gubernamentales" y su calendario "2026 bank holidays"):
  - La colocacion (liquidacion) es siempre en jueves; si es inhabil, se adelanta al dia habil anterior.
  - La subasta se hace dos dias habiles antes de la colocacion (normalmente el martes).
  - Dias inhabiles bancarios: 1 de enero, primer lunes de febrero, tercer lunes de marzo, jueves y viernes santos,
    1 de mayo, 16 de septiembre, 2 de noviembre, tercer lunes de noviembre, 12 y 25 de diciembre, sabados y domingos.
shortcut: estas reglas solo estan contrastadas con el calendario de Banxico de 2026; otros anios pueden traer dias
extra, asi que hay que revisar su calendario antes de cada anio (en el modelo de datos es la tabla dias_inhabiles).
"""
from datetime import date, timedelta
from functools import lru_cache

BUSINESS_DAYS_BEFORE_PLACEMENT = 2  # la subasta es dos dias habiles antes de la colocacion
PLACEMENT_WEEKDAY = 3  # jueves (0 = lunes)


def _easter(year):
    """Domingo de Pascua (algoritmo gregoriano anonimo)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_monday(year, month, n):
    first = date(year, month, 1)
    return first + timedelta(days=(0 - first.weekday()) % 7, weeks=n - 1)


@lru_cache(maxsize=None)
def bank_holidays(year):
    easter = _easter(year)
    return frozenset({
        date(year, 1, 1), _nth_monday(year, 2, 1), _nth_monday(year, 3, 3),
        easter - timedelta(days=3), easter - timedelta(days=2),  # jueves y viernes santos
        date(year, 5, 1), date(year, 9, 16), date(year, 11, 2), _nth_monday(year, 11, 3),
        date(year, 12, 12), date(year, 12, 25),
    })


def is_business_day(day):
    return day.weekday() < 5 and day not in bank_holidays(day.year)


def business_days_before(day, n):
    """El dia que queda `n` dias habiles antes de `day` (cuenta sabados, domingos y los inhabiles bancarios)."""
    while n:
        day -= timedelta(days=1)
        if is_business_day(day):
            n -= 1
    return day


def _thursday_of_week(day):
    return day - timedelta(days=day.weekday()) + timedelta(days=PLACEMENT_WEEKDAY)


def placement_date(day):
    """Colocacion de la semana de `day`: su jueves, o el dia habil anterior si ese jueves es inhabil."""
    placement = _thursday_of_week(day)
    while not is_business_day(placement):
        placement -= timedelta(days=1)
    return placement


def auction_date(placement):
    return business_days_before(placement, BUSINESS_DAYS_BEFORE_PLACEMENT)


def auction_for_week(day):
    """La subasta cuya colocacion cae en la semana de `day`."""
    return auction_date(placement_date(day))


def placement_of_auction(auction):
    """La colocacion (liquidacion) de la subasta del dia `auction`."""
    for weeks in (0, 1, -1):
        placement = placement_date(auction + timedelta(weeks=weeks))
        if auction_date(placement) == auction:
            return placement
    return placement_date(auction)


def next_registrable_auction(today):
    """Subasta a la que entra una orden de hoy: la primera cuyo dia habil anterior no ha pasado."""
    for weeks in range(6):
        auction = auction_for_week(today + timedelta(weeks=weeks))
        if business_days_before(auction, 1) >= today:
            return auction
    raise ValueError("Sin subasta proxima")


def auction_settling_on(day):
    """La subasta cuya colocacion es `day` (o la primera posterior, si `day` no es dia de colocacion)."""
    for weeks in range(-1, 6):
        placement = placement_date(day + timedelta(weeks=weeks))
        if placement >= day:
            return auction_date(placement)
    raise ValueError("Sin subasta proxima")
