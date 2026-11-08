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


class DiasInhabilesTest(unittest.TestCase):
    BONO = {"symbol": "BONOM3", "nominal_value": 100, "term_days": 1092, "coupon_days": 182, "kind": "bono_m"}

    def test_el_1_de_octubre_solo_es_inhabil_cada_seis_anios(self):
        self.assertIn(date(2030, 10, 1), calendar_mx.bank_holidays(2030))
        self.assertIn(date(2024, 10, 1), calendar_mx.bank_holidays(2024))
        self.assertNotIn(date(2026, 10, 1), calendar_mx.bank_holidays(2026))
        self.assertNotIn(date(2027, 10, 1), calendar_mx.bank_holidays(2027))

    def test_lo_que_cae_en_inhabil_se_paga_el_dia_habil_anterior(self):
        self.assertEqual(calendar_mx.previous_business_day(date(2026, 12, 25)), date(2026, 12, 24))  # viernes inhabil
        self.assertEqual(calendar_mx.previous_business_day(date(2026, 11, 2)), date(2026, 10, 30))  # lunes inhabil: el viernes
        self.assertEqual(calendar_mx.previous_business_day(date(2026, 11, 5)), date(2026, 11, 5))

    def test_un_vencimiento_nominal_inhabil_se_paga_el_dia_habil_anterior(self):
        cetes = {"symbol": "CETES28", "nominal_value": 10, "term_days": 28, "kind": "cetes"}
        lot = bond_math.new_lot(cetes, 100, "CETES 28", 6.0, date(2026, 11, 27), "l")  # 27 nov. + 28 dias = viernes 25 de dic.
        self.assertEqual(lot["maturity_date"], "2026-12-24")

    def test_el_cupon_que_cae_en_inhabil_se_corre_y_cuenta_los_dias_reales(self):
        # Compra el 26 de junio de 2026: 182 dias despues es el 25 de diciembre (inhabil), el cupon se paga el 24.
        lot = bond_math.new_lot(self.BONO, 1000, "Bono M 3", 8.0, date(2026, 6, 26), "l")
        schedule = bond_math.coupon_schedule(lot)
        self.assertEqual((schedule[0], lot["next_coupon_date"]), (date(2026, 12, 24), "2026-12-24"))
        self.assertEqual(schedule[-1], date.fromisoformat(lot["maturity_date"]))
        self.assertEqual(bond_math.coupon_amount(lot), round(100 * 1000 * 0.08 * 181 / 360, 2))  # 181 dias, no 182
        self.assertEqual(bond_math.coupon_amount(lot, 2), round(100 * 1000 * 0.08 * (schedule[1] - schedule[0]).days / 360, 2))

    def test_el_motor_paga_el_cupon_en_la_fecha_corrida(self):
        lot = bond_math.new_lot(self.BONO, 1000, "Bono M 3", 8.0, date(2026, 6, 26), "l")
        portfolio, events = {"cash": 0.0, "holdings": [lot]}, []
        bond_engine._pay_coupons(portfolio, lot, date(2026, 12, 23), events, [])  # un dia antes: nada
        self.assertEqual((portfolio["cash"], lot["coupons_paid"]), (0.0, 0))
        bond_engine._pay_coupons(portfolio, lot, date(2026, 12, 24), events, [])
        self.assertEqual((portfolio["cash"], lot["coupons_paid"]), (round(100 * 1000 * 0.08 * 181 / 360, 2), 1))
        self.assertEqual(lot["next_coupon_date"], bond_math.coupon_schedule(lot)[1].isoformat())


class MercadoTest(unittest.TestCase):
    """Vector de precios 'on the run' de Banxico del 6 de noviembre de 2026 (estructura CF300 del SIE)."""
    VECTOR = {
        "SF45422": 27, "SF45470": 6.300028, "SF45423": 90, "SF45471": 6.469986, "SF45424": 174, "SF45472": 6.532553,
        "SF45425": 342, "SF45473": 6.802247, "SF349886": 692, "SF349889": 7.64,
        "SF45427": 1210, "SF45448": 101.867622, "SF45475": 8.5,
        "SF45428": 1987, "SF45450": 98.039385, "SF45476": 8.0,
        "SF45430": 3394, "SF45454": 93.0567, "SF45478": 8.0,
        "SF45431": 5851, "SF45456": 84.556731, "SF45479": 7.75,
        "SF60720": 10401, "SF60721": 83.023065, "SF60723": 8.0,
    }

    def test_los_cetes_del_vector_cuadran_con_su_precio_publicado(self):
        for term, rate, published in ((27, 6.300028, 9.952972), (90, 6.469986, 9.840825), (174, 6.532553, 9.693924),
                                      (342, 6.802247, 9.393011), (692, 7.64, 8.719477)):
            self.assertAlmostEqual(10 / (1 + rate / 100 * term / 360), published, places=6)

    def test_los_intereses_devengados_del_vector_cuadran_con_la_formula(self):
        # precio sucio - precio limpio publicado, por titulo
        for coupon, term, published in ((8.5, 1210, 103.378733 - 101.867622), (8.0, 1987, 98.372718 - 98.039385),
                                        (8.0, 3394, 94.478922 - 93.0567), (7.75, 5851, 87.893537 - 84.556731),
                                        (8.0, 10401, 86.467509 - 83.023065)):
            self.assertAlmostEqual(bond_math.bono_accrued(coupon, term), published, places=5)

    def test_el_rendimiento_que_da_un_precio_limpio_lo_regresa_a_ese_precio(self):
        y = bond_math.bono_yield_from_clean_price(97.45968, 7.0, 1036)
        self.assertAlmostEqual(y, 8.0, places=3)  # ejemplo de Banxico: cupon 7 %, rendimiento 8 %
        self.assertAlmostEqual(bond_math.bono_clean_price(7.0, 8.0, 1036), 97.45968, places=5)

    def test_la_curva_del_dia_sale_del_vector(self):
        curve = bond_math.curve_from_vector(self.VECTOR)
        self.assertEqual([t for t, _ in curve["cetes"]], [27, 90, 174, 342, 692])
        self.assertEqual([t for t, _ in curve["bono_m_curve"]], [1210, 1987, 3394, 5851, 10401])  # el rango de 5 a 7 anios no cotiza
        self.assertAlmostEqual(dict(curve["bono_m_curve"])[1210], 7.85, places=2)
        self.assertEqual(sorted(y for _, y in curve["bono_m_curve"]), [y for _, y in curve["bono_m_curve"]])  # curva creciente

    def test_un_bono_m_con_cupon_igual_al_rendimiento_vale_su_nominal_mas_el_devengado(self):
        # 3 cupones de 182 dias sin inhabiles en medio: todos los periodos son iguales.
        lot = bond_math.new_lot({**BONO_M5, "term_days": 546}, 1000, "Bono M", 8.0, date(2026, 11, 5), "l")
        as_of = date(2027, 1, 14)
        curve = {"cetes": [(28, 6.0)], "bono_m": {}, "bono_m_curve": [(500, 8.0), (2000, 8.0)]}
        # El dia de la compra, con rendimiento igual al cupon, el bono vale exactamente su nominal (cada periodo es a la par).
        self.assertAlmostEqual(bond_math.market_value(lot, date(2026, 11, 5), curve), 100_000, delta=0.5)
        # A mitad de un periodo la formula de Banxico capitaliza la fraccion: queda a menos de 0.3 % del devengado lineal.
        value = bond_math.market_value(lot, as_of, curve)
        self.assertAlmostEqual(value, bond_math.accrued_value(lot, as_of), delta=300)  # sobre 100,000 de nominal

    def test_con_mas_rendimiento_de_mercado_el_bono_vale_menos(self):
        lot = bond_math.new_lot(BONO_M5, 1000, "Bono M 5", 8.0, date(2026, 11, 5), "l")
        low = bond_math.market_value(lot, date(2027, 1, 14), {"cetes": [(28, 6.0)], "bono_m": {}, "bono_m_curve": [(1000, 7.0)]})
        high = bond_math.market_value(lot, date(2027, 1, 14), {"cetes": [(28, 6.0)], "bono_m": {}, "bono_m_curve": [(1000, 9.0)]})
        self.assertGreater(low, high)


BONO_M5 = {"symbol": "BONOM5", "nominal_value": 100, "term_days": 1820, "coupon_days": 182, "kind": "bono_m"}
UDIBONO = {"symbol": "UDIBONO3", "nominal_value": 100, "term_days": 1092, "coupon_days": 182, "kind": "udibono"}
BPAG28 = {"symbol": "BPAG28", "nominal_value": 100, "term_days": 1092, "coupon_days": 28, "kind": "bpa",
          "cetes_series_id": "SF43936", "tpfg_series_id": "SF43774", "price_series_id": "SF165598"}
BPA182 = {"symbol": "BPA182", "nominal_value": 100, "term_days": 2548, "coupon_days": 182, "kind": "bpa",
          "cetes_series_id": "SF43942", "price_series_id": "SF45462", "udi_protection": True}


class UdibonoTest(unittest.TestCase):
    def test_precio_del_udibono_del_ejemplo_de_banxico(self):
        # Nota tecnica de Udibonos: cupon 8 %, rendimiento 8.25 % en UDIS, 3619 dias por vencer, 21 corridos del cupon.
        self.assertEqual(round(bond_math.bono_clean_price(8.0, 8.25, 3619), 5), 98.30596)
        self.assertAlmostEqual(bond_math.bono_clean_price(8.0, 8.25, 3619) + bond_math.bono_accrued(8.0, 3619), 98.77262, places=4)

    def test_se_compra_y_cuesta_en_udis_convertidos_a_pesos(self):
        lot = bond_math.new_lot(UDIBONO, 1000, "Udibono", 4.0, date(2026, 4, 30), "u", udi=8.834487)
        self.assertEqual(lot["udi_at_purchase"], 8.834487)
        self.assertEqual(bond_math.cost(lot), round(100 * 1000 * 8.834487, 2))  # 100 UDIS por titulo
        self.assertEqual(bond_math.unit_cost(lot), 100 * 8.834487)

    def test_el_cupon_y_el_vencimiento_se_pagan_en_pesos_con_la_udi_del_dia(self):
        lot = bond_math.new_lot(UDIBONO, 1000, "Udibono", 4.0, date(2026, 4, 30), "u", udi=8.834487)
        udis = 100 * 1000 * 0.04 * 182 / 360  # 2022.22 UDIS
        self.assertEqual(bond_math.coupon_amount(lot, udi=8.870416), round(udis * 8.870416, 2))
        self.assertEqual(bond_math.maturity_value(lot, 9.5), round(100 * 1000 * 9.5, 2))
        portfolio, events = {"cash": 0.0, "holdings": [lot]}, []
        with mock.patch.object(bond_engine, "get_udi", return_value=8.870416):
            bond_engine._pay_coupons(portfolio, lot, date(2026, 10, 29), events, [], UDIBONO)
        self.assertEqual((portfolio["cash"], lot["coupons_paid"]), (round(udis * 8.870416, 2), 1))

    def test_al_vencer_el_udibono_paga_100_udis_por_titulo_con_la_udi_del_vencimiento(self):
        lot = bond_math.new_lot(UDIBONO, 1000, "Udibono", 4.0, date(2023, 4, 28), "u", udi=7.5)
        portfolio, events = {"cash": 0.0, "holdings": [lot]}, []
        bond_engine._redeem_lot(portfolio, lot, events, 8.9)
        self.assertEqual(portfolio["cash"], round(100 * 1000 * 8.9, 2))
        self.assertEqual(events[0]["realized_pnl_mxn"], round(100 * 1000 * 8.9 - 100 * 1000 * 7.5, 2))  # ganancia por inflacion

    def test_sin_la_udi_del_dia_el_cupon_espera(self):
        lot = bond_math.new_lot(UDIBONO, 1000, "Udibono", 4.0, date(2026, 4, 30), "u", udi=8.834487)
        portfolio = {"cash": 0.0, "holdings": [lot]}
        with mock.patch.object(bond_engine, "get_udi", side_effect=ValueError("sin dato")):
            paid = bond_engine._pay_coupons(portfolio, lot, date(2026, 10, 29), [], [], UDIBONO)
        self.assertEqual((paid, portfolio["cash"], lot["coupons_paid"]), (False, 0.0, 0))

    def test_el_valor_de_mercado_usa_el_rendimiento_real_y_la_udi_de_hoy(self):
        lot = bond_math.new_lot(UDIBONO, 1000, "Udibono", 4.0, date(2026, 11, 5), "u", udi=8.886305)
        curve = {"cetes": [(28, 6.0)], "bono_m": {}, "udibono_curve": [(500, 4.0), (2000, 4.0)], "udi": 9.0}
        # cupon igual al rendimiento, el dia de la compra: vale su nominal en UDIS, a la UDI de hoy
        self.assertAlmostEqual(bond_math.market_value(lot, date(2026, 11, 5), curve), 100 * 1000 * 9.0, delta=20)  # periodos reales (con inhabiles) difieren unos dias de los iguales
        with self.assertRaises(ValueError):
            bond_math.market_value(lot, date(2026, 11, 5), {"cetes": [(28, 6.0)], "bono_m": {}})

    def test_la_curva_real_sale_del_vector_con_la_udi_de_su_dia(self):
        values = {"SF61784": 1028, "SF61785": 898.461113, "SF61787": 4.0, "SF45432": 3821, "SF45458": 831.604205, "SF45480": 4.0,
                  "SF45422": 27, "SF45470": 6.3}
        curve = bond_math.curve_from_vector(values, vector_udi=8.888577, udi=8.893123)  # UDI del 6 de nov. de 2026
        nodes = dict(curve["udibono_curve"])
        self.assertAlmostEqual(nodes[1028], 3.597, delta=0.01)
        self.assertAlmostEqual(nodes[3821], 4.781, delta=0.01)
        self.assertEqual(curve["udi"], 8.893123)


class BpaTest(unittest.TestCase):
    def test_bpag28_paga_la_mayor_entre_cetes_y_tpfg(self):
        self.assertEqual(bond_math.bpa_rate(4.08, 4.47), 4.47)  # emision de julio de 2011 de la ficha de Banxico
        self.assertEqual(bond_math.bpa_rate(6.5, 6.26), 6.5)
        self.assertEqual(bond_math.bpa_rate(6.504, 6.26), 6.5)  # dos decimales

    def test_bpa182_compara_cetes_con_el_cambio_de_la_udi_del_periodo(self):
        # Sin inflacion alta paga CETES; si la UDI sube mas que CETES en el periodo, paga el cambio de la UDI.
        self.assertEqual(bond_math.bpa_rate(6.85, None, 8.834487, 8.870416, 182), 6.85)
        self.assertEqual(bond_math.bpa_rate(6.0, None, 8.0, 8.4, 182), round(36000 * 0.05 / 182, 2))  # 9.89

    def test_el_cupon_es_valor_nominal_por_tasa_por_dias_reales_entre_36000(self):
        lot = bond_math.new_lot(BPAG28, 1000, "BPAG28", 6.5, date(2026, 10, 8), "b", price=99.4964)
        self.assertEqual(lot["current_rate"], 6.5)
        self.assertEqual(bond_math.cost(lot), round(99.4964 * 1000, 2))
        self.assertEqual(bond_math.coupon_amount(lot), round(100 * 1000 * 6.5 * 28 / 36000, 2))
        self.assertEqual(lot["next_coupon_date"], "2026-11-05")

    def test_al_pagar_se_fija_la_tasa_del_siguiente_periodo(self):
        lot = bond_math.new_lot(BPAG28, 1000, "BPAG28", 6.5, date(2026, 10, 8), "b", price=99.4964)
        portfolio, events = {"cash": 0.0, "holdings": [lot]}, []
        with mock.patch.object(bond_engine, "get_bpa_start_rate", return_value=6.9) as rate:
            bond_engine._pay_coupons(portfolio, lot, date(2026, 11, 5), events, [], BPAG28)
        rate.assert_called_once_with(BPAG28, date(2026, 11, 5))  # tasas vigentes al inicio del periodo que empieza
        self.assertEqual(portfolio["cash"], round(100 * 1000 * 6.5 * 28 / 36000, 2))  # el cupon pagado fue a la tasa anterior
        self.assertEqual((lot["current_rate"], lot["coupons_paid"], lot["next_coupon_date"]), (6.9, 1, "2026-12-03"))

    def test_sin_las_tasas_del_nuevo_periodo_el_cupon_espera(self):
        lot = bond_math.new_lot(BPAG28, 1000, "BPAG28", 6.5, date(2026, 10, 8), "b", price=99.4964)
        portfolio = {"cash": 0.0, "holdings": [lot]}
        with mock.patch.object(bond_engine, "get_bpa_start_rate", side_effect=ValueError("sin tasa")):
            paid = bond_engine._pay_coupons(portfolio, lot, date(2026, 11, 5), [], [], BPAG28)
        self.assertEqual((paid, portfolio["cash"], lot["current_rate"]), (False, 0.0, 6.5))

    def test_bpa182_paga_la_proteccion_de_la_udi_si_supera_a_cetes(self):
        lot = bond_math.new_lot(BPA182, 1000, "BPA182", 6.0, date(2026, 4, 30), "b", price=99.0, udi=8.0)
        portfolio, events = {"cash": 0.0, "holdings": [lot]}, []
        with mock.patch.object(bond_engine, "get_udi", return_value=8.4), \
                mock.patch.object(bond_engine, "get_bpa_start_rate", return_value=6.1):
            bond_engine._pay_coupons(portfolio, lot, date(2026, 10, 29), events, [], BPA182)
        rate = round(36000 * 0.05 / 182, 2)  # la UDI subio 5 % en el periodo: 9.89 % anual
        self.assertEqual(portfolio["cash"], round(100 * 1000 * rate / 100 * 182 / 360, 2))
        self.assertEqual((lot["current_rate"], lot["udi_period_start"]), (6.1, 8.4))

    def test_valor_de_mercado_converge_a_la_par_con_los_intereses_corridos(self):
        lot = bond_math.new_lot(BPAG28, 1000, "BPAG28", 6.5, date(2026, 10, 8), "b", price=99.4964)
        curve = {"cetes": [(28, 6.0)], "bono_m": {}, "floaters": {"BPAG28": (1000.0, 99.5451)}}
        value = bond_math.market_value(lot, date(2026, 10, 8), curve)  # el dia de la compra, sin intereses corridos
        remaining = (date.fromisoformat(lot["maturity_date"]) - date(2026, 10, 8)).days
        self.assertAlmostEqual(value / 1000, 100 - (100 - 99.5451) * min(1, remaining / 1000), places=4)
        later = bond_math.market_value(lot, date(2026, 10, 22), curve)  # 14 dias despues: 14 dias de cupon corrido
        self.assertGreater(later, value)
        with self.assertRaises(ValueError):
            bond_math.market_value(lot, date(2026, 10, 8), {"cetes": [(28, 6.0)], "bono_m": {}, "floaters": {}})


class CatalogoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "assets.json")
        with open(path, encoding="utf8") as f:
            cls.assets = json.load(f)

    def test_el_plazo_de_los_bonos_con_cupon_es_multiplo_de_su_periodo(self):
        for bond in self.assets:
            if bond["kind"] != "cetes":
                self.assertEqual(bond["term_days"] % bond["coupon_days"], 0, bond["symbol"])

    def test_cada_tipo_trae_las_series_que_su_motor_necesita(self):
        from utils import market_vector
        for bond in self.assets:
            self.assertTrue(bond["series_id"].startswith("SF"), bond["symbol"])
            if bond["kind"] == "bpa":
                self.assertIn(bond["symbol"], market_vector.FLOATERS)
                self.assertTrue(bond["cetes_series_id"] and bond["price_series_id"])
                self.assertEqual(bool(bond.get("tpfg_series_id")), not bond.get("udi_protection"))  # BPAG: TPFG; BPA182: UDI
            if bond["kind"] == "udibono":
                self.assertEqual((bond["nominal_value"], bond["unit"]), (100, "UDI"))

    def test_los_simbolos_no_se_repiten(self):
        symbols = [b["symbol"] for b in self.assets]
        self.assertEqual(len(symbols), len(set(symbols)))


if __name__ == "__main__":
    unittest.main()
