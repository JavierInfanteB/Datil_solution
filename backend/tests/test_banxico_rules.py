"""Reglas de Banxico para bonos y CETES: calendario, fechas de subasta, precios y plazos (logica pura, sin red).

Los numeros de los ejemplos salen de las notas tecnicas de Banxico (apendices de CETES, Bonos MS y Bondes D) y se
reproducen exactamente. Se corre desde backend/:  python -m unittest discover -s tests
"""
import os
import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import bond_engine, bond_math, calendar_mx  # noqa: E402


class CalendarTest(unittest.TestCase):
    def test_dias_inhabiles_de_2026_son_los_del_calendario_de_banxico(self):
        weekdays = sorted(d for d in calendar_mx.bank_holidays(2026) if d.weekday() < 5)
        self.assertEqual(weekdays, [date(2026, 1, 1), date(2026, 2, 2), date(2026, 3, 16), date(2026, 4, 2), date(2026, 4, 3),
                                    date(2026, 5, 1), date(2026, 9, 16), date(2026, 11, 2), date(2026, 11, 16), date(2026, 12, 25)])

    def test_semana_santa_sigue_a_la_pascua(self):
        self.assertEqual(calendar_mx._easter(2026), date(2026, 4, 5))
        self.assertEqual(calendar_mx._easter(2027), date(2027, 3, 28))

    def test_dias_habiles_antes_saltan_inhabiles(self):
        self.assertEqual(calendar_mx.business_days_before(date(2026, 11, 3), 1), date(2026, 10, 30))  # el lunes 2 es inhabil
        self.assertEqual(bond_math.business_days_before("2026-04-06", 1), date(2026, 4, 1))  # viernes y jueves santos

    def test_la_colocacion_es_el_jueves_y_la_subasta_dos_dias_habiles_antes(self):
        self.assertEqual(calendar_mx.placement_date(date(2026, 11, 3)), date(2026, 11, 5))
        self.assertEqual(calendar_mx.auction_for_week(date(2026, 11, 3)), date(2026, 11, 3))  # martes
        self.assertEqual(calendar_mx.placement_of_auction(date(2026, 11, 3)), date(2026, 11, 5))

    def test_jueves_inhabil_se_adelanta_al_miercoles(self):
        # El jueves 2 de abril de 2026 es jueves santo: se coloca el miercoles 1 y se subasta el lunes 30 de marzo.
        self.assertEqual(calendar_mx.placement_date(date(2026, 4, 1)), date(2026, 4, 1))
        self.assertEqual(calendar_mx.auction_for_week(date(2026, 3, 30)), date(2026, 3, 30))
        self.assertEqual(calendar_mx.placement_of_auction(date(2026, 3, 30)), date(2026, 4, 1))

    def test_un_inhabil_entre_subasta_y_colocacion_corre_la_subasta(self):
        # El miercoles 16 de septiembre es inhabil: para colocar el jueves 17 la subasta es el lunes 14.
        self.assertEqual(calendar_mx.auction_for_week(date(2026, 9, 15)), date(2026, 9, 14))
        self.assertEqual(calendar_mx.placement_of_auction(date(2026, 9, 14)), date(2026, 9, 17))

    def test_cada_subasta_de_un_anio_se_mapea_a_su_colocacion_y_viceversa(self):
        day = date(2026, 1, 1)
        while day.year == 2026:
            placement = calendar_mx.placement_date(day)
            self.assertTrue(calendar_mx.is_business_day(placement))
            auction = calendar_mx.auction_date(placement)
            self.assertEqual(calendar_mx.placement_of_auction(auction), placement)
            self.assertEqual(calendar_mx.auction_settling_on(placement), auction)
            day += timedelta(days=7)

    def test_la_orden_entra_a_la_primera_subasta_cuyo_dia_habil_anterior_no_paso(self):
        self.assertEqual(calendar_mx.next_registrable_auction(date(2026, 11, 9)), date(2026, 11, 10))
        self.assertEqual(calendar_mx.next_registrable_auction(date(2026, 11, 10)), date(2026, 11, 17))
        self.assertEqual(calendar_mx.next_registrable_auction(date(2026, 3, 27)), date(2026, 3, 30))  # viernes, subasta del lunes


class BanxicoExamplesTest(unittest.TestCase):
    def test_precio_de_un_cete_por_rendimiento_y_por_descuento(self):
        # Apendice 1B de CETES: 91 dias, rendimiento 4.39 % (descuento 4.34 %), nominal 10.
        self.assertEqual(bond_math.cetes_price(10, 4.39, 91), 9.8902485)
        self.assertEqual(round(10 * (1 - 0.0434 * 91 / 360), 7), 9.8902944)

    def test_el_precio_del_cete_va_a_siete_decimales(self):
        self.assertEqual(bond_math.cetes_price(10, 6.0, 28), 9.9535501)

    def test_valor_del_bono_ms_con_cupon_corrido_es_el_precio_sucio_de_banxico(self):
        # Nota tecnica de Bonos MS: cupon 7 %, rendimiento 8 %, 1036 dias por vencer, 56 dias corridos del cupon.
        # Precio limpio 97.45968 + devengado 1.0888889 = precio sucio 98.54857 por titulo.
        as_of = date(2022, 2, 3)
        lot = {"symbol": "BONOM10", "kind": "bono_m", "nominal_value": 100, "quantity": 1_000_000, "rate_at_purchase": 7.0,
               "coupon_days": 182, "next_coupon_date": (as_of + timedelta(days=126)).isoformat(),
               "maturity_date": (as_of + timedelta(days=1036)).isoformat(), "purchase_date": "2021-12-09"}
        value = bond_math.market_value(lot, as_of, {"cetes": [], "bono_m": {"BONOM10": 8.0}})
        self.assertAlmostEqual(value / lot["quantity"], 98.54857, delta=0.00002)

    def test_titulos_asignados_y_importe_del_ejemplo_de_bondes_d(self):
        # 400 millones entre 99.995573333333 = 4,000,177 titulos y un importe de 399,999,992.55.
        titles = bond_math.titles_for_amount(400_000_000, 99.995573333333)
        self.assertEqual(titles, 4_000_177)
        self.assertEqual((Decimal(titles) * Decimal("99.995573333333")).quantize(Decimal("0.01")), Decimal("399999992.55"))

    def test_un_monto_ya_redondeado_a_centavos_no_pierde_un_titulo(self):
        price = bond_math.cetes_price(10, 6.0, 28)  # 9.9535501
        self.assertEqual(bond_math.titles_for_amount(9953.55, price), 1000)  # 1000 titulos cuestan 9953.55 redondeado
        self.assertEqual(bond_math.titles_for_amount(9953.54, price), 999)


class PlazoRealTest(unittest.TestCase):
    CETES182 = {"symbol": "CETES182", "nominal_value": 10, "term_days": 182, "kind": "cetes", "term_series_id": "SF43941"}

    def _execute(self, term):
        order = {"symbol": "CETES182", "name": "CETES 182", "quantity": None, "amount_mxn": 1000.0,
                 "scheduled_date": "2026-11-03"}
        portfolio = {"cash": 1000.0, "holdings": []}
        with mock.patch.object(bond_engine, "get_bond_auction_rate", return_value=6.0), \
                mock.patch.object(bond_engine, "get_bond_auction_term", return_value=term):
            status, _ = bond_engine._execute_order(portfolio, order, {"CETES182": self.CETES182}, [])
        return status, portfolio["holdings"][0]

    def test_el_vencimiento_usa_el_plazo_real_que_publica_banxico(self):
        status, lot = self._execute(175)  # el CETE de 182 salio a 175 dias en la subasta del 5 de nov. de 2026
        self.assertEqual((status, lot["purchase_date"], lot["maturity_date"]), ("executed", "2026-11-05", "2027-04-29"))
        self.assertEqual(date.fromisoformat(lot["maturity_date"]).weekday(), 3)  # jueves
        self.assertEqual(lot["purchase_price"], bond_math.cetes_price(10, 6.0, 175))

    def test_sin_serie_de_plazo_se_usa_el_plazo_nominal(self):
        order = {"symbol": "CETES28", "name": "CETES 28", "quantity": None, "amount_mxn": 1000.0, "scheduled_date": "2026-11-03"}
        bond = {"symbol": "CETES28", "nominal_value": 10, "term_days": 28, "kind": "cetes"}
        portfolio = {"cash": 1000.0, "holdings": []}
        with mock.patch.object(bond_engine, "get_bond_auction_rate", return_value=6.0):
            bond_engine._execute_order(portfolio, order, {"CETES28": bond}, [])
        self.assertEqual(portfolio["holdings"][0]["maturity_date"], "2026-12-03")


if __name__ == "__main__":
    unittest.main()
