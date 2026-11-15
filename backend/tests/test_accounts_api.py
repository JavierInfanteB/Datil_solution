"""Roles, puestos y panel del consultor contra una app de Flask con datos temporales.

Corre contra PostgreSQL real (rol datil_app). Requiere TEST_DB_NAME (base desechable: se borra su esquema `datil`).
Desde backend/:  python -m unittest discover -s tests
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pgfixture  # noqa: E402
from flask import Flask  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from routes import register_routes  # noqa: E402
from config import Config  # noqa: E402
from utils import alerts, bond_engine, cifrado, ideas, telegram  # noqa: E402

telegram_real_call = telegram._call  # la funcion real, antes de que las pruebas la reemplacen

LOTE_2 = "00000000-0000-4000-8000-000000000002"
ORDEN_1 = "00000000-0000-4000-8000-0000000000a1"
PASSWORD = "clave-de-prueba-1"
PASSWORD_HASH = generate_password_hash(PASSWORD)  # scrypt es lento a proposito: una sola vez para todas las pruebas
USERS = [
    {"id": 1, "username": "root", "name": "Root", "role": "admin"},
    {"id": 2, "username": "ana", "name": "Ana", "role": "consultor", "puesto": "Consultor"},
    {"id": 3, "username": "beto", "name": "Beto", "role": "usuario", "puesto": "Inversionista", "consultant": "ana"},
    {"id": 4, "username": "carla", "name": "Carla", "role": "usuario", "puesto": "Inversionista", "consultant": "dora"},
    {"id": 5, "username": "dora", "name": "Dora", "role": "consultor", "puesto": "Consultor"},
]


def fake_view(username, settle=True):
    assert settle is False, "el consultor no debe ejecutar ordenes de sus clientes"
    return {"portfolio_total": 1000.0, "holdings_count": 1, "cash": 100.0, "holdings": [
        {"symbol": "AAPL", "name": "Apple", "type": "accion", "value": 1100.0, "gain_percent": 12.5, "gain_mxn": 100.0}]}


def fake_risk(username, view=None):
    return {
        "total": 1000.0, "incomplete": False, "history": None, "scenarios": [],
        "stocks": {"share": 90.0, "level": "alto", "weighted_score": 70.0, "positions": [
            {"symbol": "AAPL", "name": "Apple", "weight": 60.0, "score": 70.0, "level": "alto"}]},
        "concentration": {"cash_share": 10.0, "currency_exposure": {"MXN": 10.0, "USD": 90.0}},
    }


def losing_view(username, settle=True):
    """AAPL costo $1,000 y vale $900: -10%."""
    return {"portfolio_total": 900.0, "holdings_count": 1, "cash": 0.0, "holdings": [
        {"symbol": "AAPL", "name": "Apple", "type": "accion", "value": 900.0, "gain_mxn": -100.0, "gain_percent": -10.0}]}


class _World:
    """Estado de la prueba con la forma de los JSON originales, respaldado por PostgreSQL.

    write_json reemplaza el mundo (siembra la base por el importador real); read_json lee de la base lo que la app escribio.
    """

    def __init__(self):
        self.files = {}

    def reset(self, files):
        self.files = dict(files)
        pgfixture.load_json_files(self.files)

    def write_json(self, name, content):
        """Cambia una parte del mundo (cartera u ordenes) conservando lo que la app ya escribio en la otra."""
        other = "orders.json" if name == "portfolios.json" else "portfolios.json"
        self.files[other] = self.read_json(other)
        self.files[name] = content
        pgfixture.load_json_files(self.files)

    def read_json(self, name):
        from db import portfolio as pf
        names = [u["username"] for u in self.files["users.json"]["users"] if u["role"] == "usuario"]
        if name == "portfolios.json":
            return {n: pf.get_portfolio(n) for n in names}
        if name == "orders.json":
            return {n: pf.list_orders(n) for n in names if pf.list_orders(n)}
        raise KeyError(name)


data_store = _World()


@unittest.skipUnless(pgfixture.configured(), "define TEST_DB_NAME para correr contra PostgreSQL")
class AccountsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pgfixture.ensure_schema()

    def setUp(self):
        users = [{**u, "password_hash": PASSWORD_HASH} for u in USERS]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        earlier = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        data_store.reset({
            "users.json": {"users": users},
            "permissions.json": {},
            "orders.json": {},
            "assets.json": [{"symbol": "CETES28", "name": "CETES 28 días", "type": "bono", "kind": "cetes", "series_id": "SF43936",
                             "nominal_value": 10, "term_days": 28},
                            {"symbol": "BONOM10", "name": "Bono M 10 años", "type": "bono", "kind": "bono_m", "series_id": "SF44071",
                             "nominal_value": 100, "term_days": 3640, "coupon_days": 182}],
            "portfolios.json": {"beto": {"cash": 100, "holdings": []}},
            # Sin puestos.json: se usan los puestos de arranque.
            "transactions.json": {"beto": [
                {"id": "t1", "date": earlier, "type": "accion", "side": "buy", "symbol": "AAPL", "name": "Apple",
                 "quantity": 1, "price": 500.0, "total_mxn": 500.0},
                {"id": "t2", "date": now, "type": "accion", "side": "sell", "symbol": "AAPL", "name": "Apple",
                 "quantity": 1, "price": 600.0, "total_mxn": 600.0, "realized_pnl_mxn": 100.0},
            ]},
        })

        app = Flask(__name__)
        register_routes(app)
        self.http = app.test_client()

    def as_user(self, username):
        response = self.http.post("/api/auth/login", json={"username": username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    # ---------------------------------------------------------------- permisos

    def test_el_puesto_da_los_modulos_y_el_usuario_no_ve_permisos(self):
        modules = self.http.get("/api/permissions/me", headers=self.as_user("beto")).get_json()["modules"]
        self.assertEqual(set(modules), {"portfolio", "trading", "risk", "avisos", "plan"})
        self.assertEqual(self.http.get("/api/permissions", headers=self.as_user("beto")).status_code, 403)

    def test_cada_rol_ve_solo_sus_modulos_personales(self):
        def modules(who):
            return set(self.http.get("/api/permissions/me", headers=self.as_user(who)).get_json()["modules"])

        self.assertEqual(modules("ana"), {"consultor"})
        admin = modules("root")
        self.assertIn("permissions", admin)
        self.assertTrue({"consultor", "avisos"}.isdisjoint(admin))  # ni el admin ve "Mis clientes" ni la bandeja

        # Darle "consultor" a un usuario no le abre el panel: el rol decide.
        self.http.put("/api/permissions/beto", headers=self.as_user("root"), json={"modules": ["consultor"]})
        self.assertNotIn("consultor", modules("beto"))

    def test_cambiar_un_puesto_llega_a_todos_sus_miembros(self):
        admin = self.as_user("root")
        self.http.put("/api/permissions/puestos/Inversionista", headers=admin, json={"modules": ["portfolio"]})
        for who in ("beto", "carla"):
            modules = self.http.get("/api/permissions/me", headers=self.as_user(who)).get_json()["modules"]
            self.assertEqual(modules, ["portfolio"])

    def test_no_se_borra_un_puesto_en_uso(self):
        admin = self.as_user("root")
        self.assertEqual(self.http.delete("/api/permissions/puestos/Inversionista", headers=admin).status_code, 409)
        self.http.put("/api/permissions/puestos/Practicante", headers=admin, json={"modules": ["portfolio", "x"]})
        deleted = self.http.delete("/api/permissions/puestos/Practicante", headers=admin)
        self.assertEqual(deleted.status_code, 200)

    # ----------------------------------------------------------- usuarios (admin)

    def test_solo_el_admin_administra_usuarios(self):
        for who in ("beto", "ana"):
            self.assertEqual(self.http.get("/api/users", headers=self.as_user(who)).status_code, 403)

    def test_alta_de_usuario_valida_y_deja_entrar(self):
        admin = self.as_user("root")
        short = self.http.post("/api/users", headers=admin, json={"username": "eva", "name": "Eva", "password": "corta"})
        self.assertEqual(short.status_code, 400)
        taken = self.http.post("/api/users", headers=admin, json={"username": "beto", "name": "X", "password": PASSWORD})
        self.assertEqual(taken.status_code, 409)
        created = self.http.post("/api/users", headers=admin, json={
            "username": "eva", "name": "Eva", "password": PASSWORD, "role": "usuario",
            "puesto": "Inversionista", "consultant": "ana"})
        self.assertEqual(created.status_code, 201)
        self.assertNotIn("password_hash", created.get_json())
        self.as_user("eva")

    def test_asignacion_solo_de_usuarios_a_consultores(self):
        admin = self.as_user("root")
        to_user = self.http.patch("/api/users/beto", headers=admin, json={"consultant": "carla"})
        self.assertEqual(to_user.status_code, 400)
        consultant_as_client = self.http.patch("/api/users/ana", headers=admin, json={"consultant": "dora"})
        self.assertEqual(consultant_as_client.status_code, 400)
        moved = self.http.patch("/api/users/beto", headers=admin, json={"consultant": "dora"})
        self.assertEqual(moved.get_json()["consultant"], "dora")

    def test_el_admin_no_cambia_su_propio_rol(self):
        response = self.http.patch("/api/users/root", headers=self.as_user("root"), json={"role": "usuario"})
        self.assertEqual(response.status_code, 400)

    def test_un_consultor_degradado_suelta_a_sus_clientes_y_pierde_el_acceso_al_instante(self):
        admin, ana = self.as_user("root"), self.as_user("ana")
        with mock.patch("modules.consultant.build_portfolio_view", fake_view), \
                mock.patch("modules.consultant.portfolio_risk_for", fake_risk):
            self.assertEqual(self.http.get("/api/consultant/dashboard", headers=ana).status_code, 200)
            self.http.patch("/api/users/ana", headers=admin, json={"role": "usuario"})
            self.assertEqual(self.http.get("/api/consultant/dashboard", headers=ana).status_code, 403)
        beto = next(u for u in self.http.get("/api/users", headers=admin).get_json()["users"] if u["username"] == "beto")
        self.assertIsNone(beto["consultant"])

    # ------------------------------------------------- riesgo: nivel para el cliente, detalle para el consultor

    def test_el_cliente_solo_recibe_el_nivel_de_riesgo_y_el_consultor_el_detalle(self):
        def risk_con_estres(username, view=None):
            return {**fake_risk(username, view), "stress": {"loss_percent": 41.5, "loss_mxn": 415.0}}

        with mock.patch("modules.risk.portfolio_risk_for", risk_con_estres), \
                mock.patch("modules.consultant.build_portfolio_view", fake_view), \
                mock.patch("modules.consultant.portfolio_risk_for", risk_con_estres):
            cliente = self.http.get("/api/risk/portfolio", headers=self.as_user("beto"))
            self.assertEqual(cliente.status_code, 200)
            self.assertEqual(cliente.get_json(), {"summary_only": True, "level": "alto"})  # sin puntaje, historial, VaR, estres ni escenarios

            detalle = self.http.get("/api/consultant/clients/beto", headers=self.as_user("ana")).get_json()["risk"]
            self.assertEqual(detalle["stress"]["loss_mxn"], 415.0)
            self.assertEqual(detalle["stocks"]["weighted_score"], 70.0)

    def test_un_cliente_sin_acciones_recibe_nivel_vacio_no_un_error(self):
        def sin_acciones(username, view=None):
            return {**fake_risk(username, view), "stocks": {"share": 0.0, "level": None, "weighted_score": None, "positions": []}}

        with mock.patch("modules.risk.portfolio_risk_for", sin_acciones):
            respuesta = self.http.get("/api/risk/portfolio", headers=self.as_user("beto"))
        self.assertEqual((respuesta.status_code, respuesta.get_json()), (200, {"summary_only": True, "level": None}))

    # ------------------------------------------------------------- consultor

    def test_el_usuario_no_entra_al_panel_aunque_se_le_de_el_modulo(self):
        admin = self.as_user("root")
        self.http.put("/api/permissions/beto", headers=admin, json={"modules": ["consultor"]})
        response = self.http.get("/api/consultant/dashboard", headers=self.as_user("beto"))
        self.assertEqual(response.status_code, 403)

    def test_el_consultor_sin_el_modulo_no_entra(self):
        admin = self.as_user("root")
        self.http.put("/api/permissions/puestos/Consultor", headers=admin, json={"modules": []})
        self.assertEqual(self.http.get("/api/consultant/dashboard", headers=self.as_user("ana")).status_code, 403)

    def test_el_consultor_solo_ve_a_sus_clientes_y_sin_ejecutar_ordenes(self):
        ana = self.as_user("ana")
        with mock.patch("modules.consultant.build_portfolio_view", fake_view), \
                mock.patch("modules.consultant.portfolio_risk_for", fake_risk):
            data = self.http.get("/api/consultant/dashboard?days=7", headers=ana).get_json()
            self.assertEqual([c["username"] for c in data["clients"]], ["beto"])
            self.assertEqual(data["totals"]["buys"], 1)
            self.assertEqual(data["totals"]["sells"], 1)
            self.assertEqual(data["totals"]["unrealized"], 100.0)
            self.assertNotIn("suggestions", data)  # las sugerencias viven solo en /feed
            self.assertEqual(len(data["activity"]), 7)
            self.assertEqual(data["top_sales"][0]["realized_pnl_mxn"], 100.0)
            self.assertEqual(data["top_positions"][0]["symbol"], "AAPL")
            self.assertEqual(self.http.get("/api/consultant/dashboard?client=beto", headers=ana).get_json()["totals"]["clients"], 1)
            feed = self.http.get("/api/consultant/feed", headers=ana).get_json()["items"]
            self.assertEqual((feed[0]["kind"], feed[0]["status"], feed[0]["symbol"]), ("sugerencia", "activa", "AAPL"))
            self.assertTrue(feed[0]["when"].startswith("20"))
            self.assertEqual(self.http.get("/api/consultant/clients/beto", headers=ana).status_code, 200)
            self.assertEqual(self.http.get("/api/consultant/clients/carla", headers=ana).status_code, 404)
            self.assertEqual(self.http.get("/api/consultant/clients/carla/timeline", headers=ana).status_code, 404)

    def test_el_admin_no_usa_el_panel_del_consultor(self):
        self.assertEqual(self.http.get("/api/consultant/dashboard", headers=self.as_user("root")).status_code, 403)

    # ---------------------------------------------------------------- avisos

    def test_el_consultor_avisa_y_el_cliente_lo_ve_y_lo_marca_leido(self):
        ana, beto = self.as_user("ana"), self.as_user("beto")
        sent = self.http.post("/api/consultant/clients/beto/notifications", headers=ana, json={
            "kind": "riesgo", "title": "AAPL pesa mucho", "message": "Conviene reducirla."})
        self.assertEqual(sent.status_code, 201)

        inbox = self.http.get("/api/notifications", headers=beto).get_json()
        self.assertEqual(inbox["unread"], 1)
        self.assertEqual((inbox["items"][0]["title"], inbox["items"][0]["from_name"]), ("AAPL pesa mucho", "Ana"))

        self.assertEqual(self.http.post(f"/api/notifications/{sent.get_json()['id']}/read", headers=beto).status_code, 200)
        self.assertEqual(self.http.get("/api/notifications", headers=beto).get_json()["unread"], 0)
        history = self.http.get("/api/consultant/clients/beto/notifications", headers=ana).get_json()
        self.assertTrue(history[0]["read"])

    def test_los_avisos_se_validan_y_son_privados(self):
        ana = self.as_user("ana")
        url = "/api/consultant/clients/beto/notifications"
        self.assertEqual(self.http.post(url, headers=ana, json={"kind": "spam", "title": "x", "message": "y"}).status_code, 400)
        self.assertEqual(self.http.post(url, headers=ana, json={"title": " ", "message": "y"}).status_code, 400)
        self.assertEqual(self.http.post(url, headers=ana, json={"title": "x" * 81, "message": "y"}).status_code, 400)
        # Solo a sus clientes: carla es de dora.
        self.assertEqual(self.http.post("/api/consultant/clients/carla/notifications", headers=ana,
                                        json={"title": "x", "message": "y"}).status_code, 404)

        self.http.post(url, headers=ana, json={"title": "Hola", "message": "Para Beto"})
        carla = self.http.get("/api/notifications", headers=self.as_user("carla")).get_json()
        self.assertEqual(carla["items"], [])  # lo de Beto no le llega a Carla
        # El consultor no tiene bandeja y el usuario no puede mandar avisos.
        self.assertEqual(self.http.get("/api/notifications", headers=ana).status_code, 403)
        self.assertEqual(self.http.post(url, headers=self.as_user("beto"), json={"title": "x", "message": "y"}).status_code, 403)

    def test_el_admin_cambia_contrasena_y_suspende(self):
        root, beto = self.as_user("root"), self.as_user("beto")
        self.assertEqual(self.http.patch("/api/users/beto", headers=root, json={"password": "corta"}).status_code, 400)
        self.assertEqual(self.http.patch("/api/users/beto", headers=root, json={"password": "otra-clave-9"}).status_code, 200)
        login = lambda pw: self.http.post("/api/auth/login", json={"username": "beto", "password": pw}).status_code
        self.assertEqual((login(PASSWORD), login("otra-clave-9")), (401, 200))

        self.assertEqual(self.http.patch("/api/users/root", headers=root, json={"disabled": True}).status_code, 400)
        self.assertEqual(self.http.patch("/api/users/beto", headers=root, json={"disabled": True}).status_code, 200)
        self.assertEqual(login("otra-clave-9"), 403)
        self.assertEqual(self.http.get("/api/permissions/me", headers=beto).status_code, 401)  # su sesion abierta cae

    def test_el_admin_opera_solo_en_nombre_de_un_cliente(self):
        root = self.as_user("root")
        order = {"symbol": "AAPL", "quantity": 1}
        self.assertEqual(self.http.post("/api/trading/buy", headers=root, json=order).status_code, 403)  # no tiene cartera
        self.assertEqual(self.http.get("/api/portfolio", headers=root).status_code, 403)
        self.assertEqual(self.http.post("/api/trading/buy", headers=root, json={**order, "client": "ana"}).status_code, 403)

        with mock.patch("modules.trading.get_current_price", return_value={"price": 10.0, "currency": "MXN"}),                 mock.patch("modules.trading.get_fx_to_mxn", return_value=1.0):
            bought = self.http.post("/api/trading/buy", headers=root, json={**order, "client": "beto"})
        self.assertEqual(bought.status_code, 200)
        with mock.patch("modules.admin.build_portfolio_view", fake_view):
            self.assertEqual(self.http.get("/api/admin/clients", headers=root).get_json()["audit"][0]["client"], "beto")
        # Un usuario sigue operando solo lo suyo, aunque mande `client`.
        self.assertEqual(self.http.get("/api/admin/clients", headers=self.as_user("beto")).status_code, 403)

    def test_el_admin_ve_a_todos_los_clientes(self):
        with mock.patch("modules.admin.build_portfolio_view", fake_view):
            rows = self.http.get("/api/admin/clients", headers=self.as_user("root")).get_json()["clients"]
        self.assertEqual({r["username"] for r in rows}, {"beto", "carla"})

    def test_niveles_de_alerta(self):
        loss = {"kind": "loss", "percent": 10}
        self.assertEqual([alerts.level_of(loss, m) for m in (None, 3, -5, -6, -8, -10)], [0, 0, 0, 1, 2, 3])
        self.assertEqual([alerts.level_of({"kind": "gain", "percent": 20}, m) for m in (-30, 12, 16, 20)], [0, 1, 2, 3])

    def test_alerta_del_cliente_avisa_al_cliente_y_el_consultor_la_ve_antes(self):
        beto, ana = self.as_user("beto"), self.as_user("ana")
        bad = {"symbol": "aapl", "kind": "loss", "percent": 0}
        self.assertEqual(self.http.post("/api/plan/alerts", headers=beto, json=bad).status_code, 400)
        mine = self.http.post("/api/plan/alerts", headers=beto, json={**bad, "percent": 10, "indication": "vender"})
        self.assertEqual(mine.status_code, 201)
        self.http.post("/api/consultant/clients/beto/alerts", headers=ana, json={**bad, "percent": 20})

        with mock.patch("modules.consultant.build_portfolio_view", losing_view):
            with mock.patch("modules.consultant.portfolio_risk_for", fake_risk):
                feed = self.http.get("/api/consultant/feed", headers=ana).get_json()["items"]
        alert_items = [i for i in feed if i["kind"] == "alerta"]
        self.assertEqual([(i["severity"], i["title"]) for i in alert_items], [("alta", "AAPL: pérdida de 10% cumplida")])
        self.assertIn("when", alert_items[0])  # la de 20% va a la mitad: no aparece aun

        inbox = self.http.get("/api/notifications", headers=beto).get_json()["items"]
        self.assertEqual(inbox[0]["title"], "Alerta cumplida: AAPL")
        self.assertIn("vender", inbox[0]["message"])
        # La que puso el consultor no es del cliente, ni al reves; y el aviso no se repite.
        alert_ids = {a["by"]: a["id"] for a in alerts.load()["beto"]}
        self.assertEqual(self.http.delete(f"/api/plan/alerts/{alert_ids['ana']}", headers=beto).status_code, 404)
        self.assertEqual(self.http.delete(f"/api/consultant/clients/beto/alerts/{alert_ids['beto']}", headers=ana).status_code, 404)
        with mock.patch("modules.consultant.build_portfolio_view", losing_view),                 mock.patch("modules.consultant.portfolio_risk_for", fake_risk):
            self.http.get("/api/consultant/feed", headers=ana)
        self.assertEqual(len(self.http.get("/api/notifications", headers=beto).get_json()["items"]), 1)

    def test_metas_y_notas_llegan_al_consultor_y_las_privadas_no_salen(self):
        beto, ana = self.as_user("beto"), self.as_user("ana")
        self.assertEqual(self.http.post("/api/plan/goals", headers=beto, json={"title": "Casa", "target_mxn": -5}).status_code, 400)
        self.http.post("/api/plan/goals", headers=beto, json={"title": "Casa", "target_mxn": 5000, "target_date": "2030-01-01"})
        self.http.post("/api/plan/notes", headers=beto, json={"text": "Quiero menos riesgo"})
        self.http.post("/api/consultant/clients/beto/private-notes", headers=ana, json={"text": "Se pone nervioso"})

        with mock.patch("modules.consultant.build_portfolio_view", losing_view):
            plan = self.http.get("/api/consultant/clients/beto/plan", headers=ana).get_json()
        self.assertEqual((plan["goals"][0]["title"], plan["notes"][0]["text"], plan["private_notes"][0]["text"]),
                         ("Casa", "Quiero menos riesgo", "Se pone nervioso"))
        self.assertEqual(self.http.get("/api/consultant/clients/beto/plan", headers=self.as_user("dora")).status_code, 404)
        # El cliente no tiene ruta para leer las notas privadas de su consultor.
        self.assertNotIn("Se pone nervioso", self.http.get("/api/plan/notes", headers=beto).get_data(as_text=True))

    def test_reporte_del_periodo(self):
        with mock.patch("modules.plan.build_portfolio_view", losing_view), mock.patch("modules.plan.portfolio_risk_for", fake_risk):
            report = self.http.get("/api/plan/report?period=quarter", headers=self.as_user("beto")).get_json()
        self.assertEqual((report["period"], report["realized"]), ("quarter", 100.0))
        self.assertEqual(report["unrealized"], -100.0)
        self.assertTrue(report["series"] and report["achievements"] and report["improvements"])

    def test_baja_solo_en_cero_y_reactivar_avisa(self):
        root = self.as_user("root")
        self.assertEqual(self.http.delete("/api/users/beto", headers=root).status_code, 409)  # tiene efectivo
        self.assertEqual(self.http.delete("/api/users/root", headers=root).status_code, 400)
        self.assertEqual(self.http.delete("/api/users/carla", headers=root).status_code, 200)
        self.assertEqual(self.http.post("/api/auth/login", json={"username": "carla", "password": PASSWORD}).status_code, 403)

        self.assertEqual(self.http.patch("/api/users/carla", headers=root, json={"disabled": False}).status_code, 200)
        inbox = self.http.get("/api/notifications", headers=self.as_user("carla")).get_json()["items"]
        self.assertEqual(inbox[0]["title"], "Tu cuenta fue reactivada")

    def test_el_admin_compara_consultores_con_resultados_y_constancia(self):
        ana = self.as_user("ana")
        self.http.post("/api/consultant/clients/beto/notifications", headers=ana, json={"title": "Hola", "message": "x"})
        with mock.patch("modules.admin.build_portfolio_view", fake_view):
            data = self.http.get("/api/admin/consultants", headers=self.as_user("root")).get_json()
        by_name = {c["name"]: c for c in data["consultants"]}
        self.assertEqual(set(by_name), {"Ana", "Dora"})
        ana_kpi = by_name["Ana"]
        self.assertEqual((ana_kpi["clients"], ana_kpi["total"], ana_kpi["in_profit"]), (1, 200.0, 1))  # 100 sin vender + 100 vendido
        self.assertEqual((ana_kpi["actions_30d"], ana_kpi["consistency"]), (1, 8))  # 1 de 12 semanas
        self.assertEqual(by_name["Dora"]["actions_30d"], 0)
        self.assertEqual(self.http.get("/api/admin/consultants", headers=ana).status_code, 403)

    def test_el_registro_dice_quien_y_por_donde_y_se_filtra_por_rol(self):
        self.http.post("/api/consultant/clients/beto/notifications", headers=self.as_user("ana"), json={"title": "Hola", "message": "x"})
        root = self.as_user("root")
        with mock.patch("modules.trading.get_current_price", return_value={"price": 10.0, "currency": "MXN"}),                 mock.patch("modules.trading.get_fx_to_mxn", return_value=1.0):
            self.http.post("/api/trading/buy", headers=root, json={"symbol": "AAPL", "quantity": 1, "client": "beto"})

        def rows(who, kind="operaciones"):
            return self.http.get(f"/api/activity?kind={kind}", headers=self.as_user(who)).get_json()

        ops = rows("root")
        self.assertEqual({(r["actor"], r["origin"]) for r in ops}, {("Beto", "cliente"), ("Root", "admin")})  # lo viejo es del cliente
        self.assertEqual({r["consultant"] for r in ops}, {"ana"})
        self.assertEqual(len(rows("beto")), 3)  # ve todo lo de su cartera, tambien lo que hizo el admin
        self.assertEqual(len(rows("ana")), 3)
        self.assertEqual(rows("dora"), [])
        self.assertEqual([r["text"] for r in rows("root", "avisos")], ["Hola"])
        self.assertEqual(rows("beto", "avisos"), [])  # el cliente tiene su bandeja de avisos, no este registro
        self.assertEqual(len(rows("ana", "avisos")), 1)
        self.assertEqual(rows("dora", "avisos"), [])

    def test_ideas_de_acciones_solo_con_motivo(self):
        flat = [("d", 100.0)] * 250
        self.assertEqual(ideas.reasons(ideas.facts(flat)), ["Cerca de su mínimo de 1.0 años (+0.0%)"])
        up = [("d", 50.0 + i * 0.1) for i in range(300)]
        self.assertTrue(any("Buena tendencia" in r for r in ideas.reasons(ideas.facts(up))))
        down = [("d", 200.0 - i * 0.3) for i in range(300)]
        self.assertEqual(ideas.reasons(ideas.facts(down)), ["Cerca de su mínimo de 1.2 años (+0.0%)"])
        middle = [("d", 100.0)] * 100 + [("d", 300.0)] * 100 + [("d", 200.0)] * 100  # lejos del minimo y bajo su promedio
        self.assertEqual(ideas.reasons(ideas.facts(middle)), [])

    # ---------------------------------------------------------------- bonos y CETES (reglas de cetesdirecto)

    CETES28 = {"symbol": "CETES28", "nominal_value": 10, "term_days": 28, "kind": "cetes"}

    def _bond_lot(self, settlement, mode, quantity=1000, lot_id="00000000-0000-4000-8000-000000000001"):
        """Un lote de CETES a 28 dias liquidado en `settlement`, con la reinversion `mode`, en la cartera de beto."""
        from utils import bond_math
        lot = bond_math.new_lot(self.CETES28, quantity, "CETES 28 días", 6.0, settlement, lot_id)
        lot["reinvest"] = mode
        data_store.write_json("portfolios.json", {"beto": {"cash": 0.0, "holdings": [lot]}})
        data_store.write_json("orders.json", {})
        return lot

    def _pending(self):
        return [o for o in data_store.read_json("orders.json").get("beto", []) if o["status"] == "pending"]

    def test_la_orden_entra_a_la_subasta_del_proximo_martes(self):
        monday, tuesday, wednesday = date(2026, 11, 9), date(2026, 11, 10), date(2026, 11, 11)
        self.assertEqual(bond_engine.next_scheduled_purchase_date(monday), tuesday)  # se registra el dia anterior
        self.assertEqual(bond_engine.next_scheduled_purchase_date(tuesday), date(2026, 11, 17))  # el martes ya no alcanza
        self.assertEqual(bond_engine.next_scheduled_purchase_date(wednesday), date(2026, 11, 17))
        # El lunes 2 de nov. es inhabil: el ultimo dia habil para la subasta del martes 3 fue el viernes 30 de oct.
        self.assertEqual(bond_engine.next_scheduled_purchase_date(date(2026, 11, 2)), tuesday)

    def test_se_compra_por_monto_y_el_plazo_corre_desde_el_jueves(self):
        tuesday = date(2026, 11, 3)
        order = {"symbol": "CETES28", "name": "CETES 28", "quantity": None, "amount_mxn": 1000.0,
                 "scheduled_date": tuesday.isoformat()}
        portfolio, events = {"cash": 1000.0, "holdings": []}, []
        with mock.patch.object(bond_engine, "get_bond_auction_rate", return_value=6.0) as rate:
            status, _ = bond_engine._execute_order(portfolio, order, {"CETES28": self.CETES28}, events)
        self.assertEqual(status, "executed")
        rate.assert_called_once_with("CETES28", tuesday)  # la tasa es la de su subasta
        lot = portfolio["holdings"][0]
        self.assertEqual(lot["quantity"], 100)  # $1,000 / $9.9535 = 100 titulos enteros
        self.assertEqual((lot["purchase_date"], lot["maturity_date"]), ("2026-11-05", "2026-12-03"))
        self.assertAlmostEqual(portfolio["cash"], 1000 - 995.36, places=2)  # lo que no alcanza para un titulo queda

    def test_sin_tasa_la_orden_espera_hasta_la_liquidacion_y_despues_falla(self):
        portfolio = {"cash": 1000.0, "holdings": []}

        def run(auction, error):
            order = {"symbol": "CETES28", "name": "x", "quantity": None, "amount_mxn": 500.0, "scheduled_date": auction.isoformat()}
            with mock.patch.object(bond_engine, "get_bond_auction_rate", side_effect=error):
                return bond_engine._execute_order(portfolio, order, {"CETES28": self.CETES28}, [])

        upcoming = bond_engine.next_scheduled_purchase_date()  # una subasta real: su liquidacion todavia no llega
        self.assertEqual(run(upcoming, ValueError("sin tasa"))[0], "pending")  # aun puede publicarse
        self.assertEqual(run(date.today() - timedelta(days=30), ValueError("sin tasa"))[0], "failed")  # no hubo subasta
        self.assertEqual(run(date.today() - timedelta(days=30), OSError("sin red"))[0], "pending")  # sin red se reintenta
        self.assertEqual(portfolio["holdings"], [])

    def test_comprar_bono_registra_la_orden_por_monto(self):
        beto = self.as_user("beto")
        buy = lambda body: self.http.post("/api/trading/buy", headers=beto, json={"symbol": "CETES28", "asset_type": "bono", **body})
        self.assertEqual(buy({"amount_mxn": 50}).status_code, 400)  # minimo $100
        self.assertEqual(buy({"quantity": 10}).status_code, 400)  # los bonos se compran por monto
        reply = buy({"amount_mxn": 1000, "reinvest": "all"})
        order = reply.get_json()["order"]
        self.assertEqual((reply.status_code, order["status"], order["amount_mxn"], order["reinvest"]), (200, "pending", 1000, "all"))
        self.assertGreater(date.fromisoformat(order["scheduled_date"]), date.today())
        self.assertEqual(date.fromisoformat(order["scheduled_date"]), bond_engine.next_scheduled_purchase_date())

    def test_una_compra_se_cancela_hasta_el_dia_anterior_a_su_subasta(self):
        data_store.write_json("orders.json", {"beto": [{"id": ORDEN_1, "symbol": "CETES28", "status": "pending", "source": "compra",
                                                        "amount_mxn": 1000.0, "created_at": "2026-11-01", "reinvest": "none",
                                                        "scheduled_date": "2026-11-10"}]})
        _, error = bond_engine.cancel_order("beto", ORDEN_1, today=date(2026, 11, 10))
        self.assertEqual(error, "Una compra solo se cancela hasta el día anterior a su subasta")
        order, error = bond_engine.cancel_order("beto", ORDEN_1, today=date(2026, 11, 9))
        self.assertEqual((order["status"], error), ("cancelled", None))

    def test_al_vencer_se_reinvierte_en_cetes_28_todo_o_solo_el_capital(self):
        settled = date.today() - timedelta(days=38)  # vencio hace 10 dias
        for n, (mode, titles) in enumerate((("all", 1004), ("same", 1000), ("none", None))):
            # un lote distinto por vuelta: un mismo lote solo vence una vez (indice unico del libro de efectivo)
            self._bond_lot(settled, mode, lot_id=f"00000000-0000-4000-8000-0000000000c{n}")
            with mock.patch.object(bond_engine, "get_bond_auction_rate", return_value=6.0):
                bond_engine.process_due_events("beto")
            portfolio = data_store.read_json("portfolios.json")["beto"]
            if titles is None:
                self.assertEqual((portfolio["holdings"], portfolio["cash"]), ([], 10000.0))
                continue
            (lot,) = portfolio["holdings"]
            self.assertEqual((lot["symbol"], lot["quantity"], lot["reinvest"]), ("CETES28", titles, mode))  # sigue renovando
            self.assertAlmostEqual(portfolio["cash"], 10000.0 - titles * 9.95355, delta=0.5)  # en "same" queda la ganancia

    def test_reinversion_minima_de_10_titulos(self):
        self._bond_lot(date.today() - timedelta(days=38), "all", quantity=5)  # paga $50: no alcanza para 10 titulos
        with mock.patch.object(bond_engine, "get_bond_auction_rate", return_value=6.0):
            bond_engine.process_due_events("beto")
        portfolio = data_store.read_json("portfolios.json")["beto"]
        self.assertEqual((portfolio["holdings"], portfolio["cash"]), ([], 50.0))
        (order,) = data_store.read_json("orders.json")["beto"]
        self.assertEqual(order["status"], "failed")

    def test_la_reinversion_se_ve_antes_y_se_cambia_hasta_3_dias_habiles_antes(self):
        thursday = date.today() + timedelta(days=(3 - date.today().weekday()) % 7 + 7)
        lot = self._bond_lot(thursday, "all", quantity=100, lot_id=LOTE_2)  # vence otro jueves, 28 dias despues
        bond_engine.process_due_events("beto")
        (order,) = self._pending()
        auction = date.fromisoformat(order["scheduled_date"])
        self.assertEqual(auction, bond_engine._auction_settling_on(lot["maturity_date"]))  # la subasta que liquida al vencer
        self.assertEqual((order["symbol"], order["source_lot_id"], order["amount_mxn"]), ("CETES28", LOTE_2, 1000.0))

        portfolios = data_store.read_json("portfolios.json")
        self.assertIsNone(bond_engine.set_lot_reinvest(portfolios["beto"], LOTE_2, "same"))
        data_store.write_json("portfolios.json", portfolios)
        bond_engine.process_due_events("beto")
        self.assertEqual([o["amount_mxn"] for o in self._pending()], [995.36])  # solo el capital

        maturity = date.fromisoformat(lot["maturity_date"])
        late = maturity - timedelta(days=1)  # miercoles: ya no se puede cambiar
        self.assertIn("3 días hábiles", bond_engine.set_lot_reinvest(portfolios["beto"], LOTE_2, "none", today=late))
        _, error = bond_engine.cancel_order("beto", order["id"], today=late)
        self.assertIn("3 días hábiles", error)

        order, error = bond_engine.cancel_order("beto", order["id"], today=maturity - timedelta(days=3))  # el lunes si
        self.assertIsNone(error)
        bond_engine.process_due_events("beto")
        self.assertEqual(self._pending(), [])  # cancelada y el lote ya no se reinvierte
        self.assertEqual(data_store.read_json("portfolios.json")["beto"]["holdings"][0]["reinvest"], "none")

    def test_se_vende_antes_hasta_3_dias_habiles_antes_del_vencimiento(self):
        from utils import bond_math
        lot = self._bond_lot(date.today() - timedelta(days=20), "none", quantity=10)
        portfolio = data_store.read_json("portfolios.json")["beto"]
        curve = {"cetes": [(28, 6.0)], "bono_m": {}}
        last = bond_math.last_change_day(lot)
        self.assertEqual(bond_engine.sellable_lots(portfolio, "CETES28", today=last), portfolio["holdings"])
        self.assertEqual(bond_engine.sellable_lots(portfolio, "CETES28", today=last + timedelta(days=1)), [])
        _, _, _, error = bond_engine.sell_bond_lots(portfolio, "CETES28", 10, curve, today=last + timedelta(days=1))
        self.assertIn("3 días hábiles", error)
        self.assertEqual(bond_math.business_days_before(date(2026, 12, 3), 3), date(2026, 11, 30))  # jueves -> lunes

    def test_vender_antes_cancela_la_reinversion(self):
        self._bond_lot(date.today(), "same", quantity=100)
        bond_engine.process_due_events("beto")
        with pgfixture.owner_conn() as conn:  # lo vendio todo: el lote deja de estar vigente
            conn.execute("UPDATE lotes_bono SET estado = 'vendido'")
        bond_engine.process_due_events("beto")
        (order,) = data_store.read_json("orders.json")["beto"]
        self.assertEqual((order["status"], order["failure_reason"]), ("cancelled", "Se vendió el lote antes de vencer"))

    def test_ordenes_de_lunes_pasan_a_martes(self):
        monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 + 7)
        data_store.write_json("portfolios.json", {"beto": {"cash": 0.0, "holdings": []}})
        data_store.write_json("orders.json", {"beto": [{"id": ORDEN_1, "symbol": "CETES28", "name": "x", "quantity": None,
                                                        "amount_mxn": 1000.0, "created_at": "2026-11-01", "source": "compra", "reinvest": "none",
                                                        "scheduled_date": monday.isoformat(), "status": "pending"}]})
        bond_engine.process_due_events("beto")
        from utils import calendar_mx
        self.assertEqual(self._pending()[0]["scheduled_date"], calendar_mx.auction_for_week(monday).isoformat())

    def test_el_cupon_del_bono_m_se_reinvierte_si_el_lote_reinvierte_todo(self):
        from utils import bond_math
        bono = {"symbol": "BONOM10", "nominal_value": 100, "term_days": 3640, "coupon_days": 182, "kind": "bono_m"}
        settled = date.today() - timedelta(days=190)  # ya pago su primer cupon hace 8 dias
        lot = bond_math.new_lot(bono, 100, "Bono M", 9.0, settled, "00000000-0000-4000-8000-0000000000b1")
        lot["reinvest"] = "all"
        data_store.write_json("portfolios.json", {"beto": {"cash": 0.0, "holdings": [lot]}})
        data_store.write_json("orders.json", {})
        with mock.patch.object(bond_engine, "get_bond_auction_rate", return_value=6.0):
            bond_engine.process_due_events("beto")
        portfolio = data_store.read_json("portfolios.json")["beto"]
        coupon = bond_math.coupon_amount(lot)  # $455
        cetes = [h for h in portfolio["holdings"] if h["symbol"] == "CETES28"]
        self.assertEqual([h["quantity"] for h in cetes], [int(coupon // 9.95355)])
        self.assertLess(portfolio["cash"], 10)  # el cupon se invirtio


class TelegramTest(AccountsApiTest):
    """Avisos por Telegram: enlazar el chat y recibir ahi lo que entra a la bandeja. Telegram nunca se llama de verdad."""

    def setUp(self):
        super().setUp()
        for name, value in (("TELEGRAM_TOKEN", "123:token-de-prueba"), ("CIFRADO_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")):
            patcher = mock.patch.object(Config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.updates = []   # lo que "contesta" getUpdates
        self.sent = []      # mensajes mandados: (chat_id, texto)

        def fake_call(method, **params):
            if method == "getMe":
                return {"username": "bot_de_prueba"}
            if method == "getUpdates":
                return self.updates
            if method == "sendMessage":
                self.sent.append((params["chat_id"], params["text"]))  # chat_id llega como entero
                return {}

        for name, value in (("_call", fake_call), ("_bot_username", None)):
            patcher = mock.patch.object(telegram, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Sin hilos: el envio ocurre en el momento y la prueba lo ve.
        patcher = mock.patch.object(telegram.threading, "Thread", lambda target, args, kwargs, daemon: mock.Mock(start=lambda: target(*args, **kwargs)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def start_message(self, username, chat_id):
        return {"update_id": len(self.updates) + 1, "message": {"chat": {"id": chat_id}, "text": f"/start {telegram.link_code(username)}"}}

    def notify_beto(self):
        return self.http.post("/api/consultant/clients/beto/notifications", headers=self.as_user("ana"),
                              json={"kind": "riesgo", "title": "Revisa AAPL", "message": "Bajó mucho esta semana."})

    def test_enlazar_y_recibir_un_aviso(self):
        beto = self.as_user("beto")
        status = self.http.get("/api/notifications/telegram", headers=beto).get_json()
        self.assertEqual(status, {"available": True, "linked": False,
                                  "url": f"https://t.me/bot_de_prueba?start={telegram.link_code('beto')}"})

        # Antes de tocar Iniciar en el bot no hay nada que enlazar.
        self.assertEqual(self.http.post("/api/notifications/telegram", headers=beto).status_code, 404)

        self.updates.append(self.start_message("beto", 555))
        linked = self.http.post("/api/notifications/telegram", headers=beto)
        self.assertEqual(linked.status_code, 200)
        self.assertTrue(linked.get_json()["linked"])
        self.assertEqual(self.sent[-1][0], 555)  # mensaje de confirmacion

        self.assertEqual(self.notify_beto().status_code, 201)
        chat_id, text = self.sent[-1]
        self.assertEqual(chat_id, 555)
        self.assertIn("Revisa AAPL", text)
        self.assertIn("Bajó mucho esta semana.", text)
        self.assertIn("Ana", text)

    def test_el_chat_se_guarda_cifrado_y_atado_a_su_usuario(self):
        self.updates.append(self.start_message("beto", 555))
        self.http.post("/api/notifications/telegram", headers=self.as_user("beto"))
        with pgfixture.owner_conn() as conn:
            stored = conn.execute("SELECT telegram_chat_cifrado FROM usuarios WHERE usuario = 'beto'").fetchone()["telegram_chat_cifrado"]
            self.assertTrue(stored.startswith("v1:"))
            self.assertNotIn("555", stored)
            # El valor de beto copiado a la fila de carla no descifra: carla sigue sin Telegram.
            conn.execute("UPDATE usuarios SET telegram_chat_cifrado = %s WHERE usuario = 'carla'", (stored,))
        self.assertFalse(self.http.get("/api/notifications/telegram", headers=self.as_user("carla")).get_json()["linked"])
        # Con otra clave tampoco: no se manda nada.
        with mock.patch.object(Config, "CIFRADO_KEY", "ZmVkY2JhOTg3NjU0MzIxMGZlZGNiYTk4NzY1NDMyMTA="):
            self.sent.clear()
            self.notify_beto()
            self.assertEqual(self.sent, [])

    def test_cifrar_dos_veces_da_textos_distintos(self):
        a, b = cifrado.cifrar("555", "ctx"), cifrado.cifrar("555", "ctx")
        self.assertNotEqual(a, b)  # nonce aleatorio
        self.assertEqual((cifrado.descifrar(a, "ctx"), cifrado.descifrar(b, "ctx")), ("555", "555"))
        with self.assertRaises(cifrado.CifradoError):
            cifrado.descifrar(a[:-4] + "AAAA", "ctx")  # alterado

    def test_sin_clave_de_cifrado_no_se_enlaza_ni_se_guarda_en_claro(self):
        beto = self.as_user("beto")
        self.updates.append(self.start_message("beto", 555))
        with mock.patch.object(Config, "CIFRADO_KEY", ""):
            self.assertFalse(self.http.get("/api/notifications/telegram", headers=beto).get_json()["available"])
            self.assertEqual(self.http.post("/api/notifications/telegram", headers=beto).status_code, 503)
        with pgfixture.owner_conn() as conn:
            self.assertIsNone(conn.execute("SELECT telegram_chat_cifrado FROM usuarios WHERE usuario = 'beto'").fetchone()["telegram_chat_cifrado"])

    def test_el_codigo_de_otro_usuario_no_enlaza(self):
        self.updates.append(self.start_message("carla", 777))
        self.assertEqual(self.http.post("/api/notifications/telegram", headers=self.as_user("beto")).status_code, 404)
        self.assertNotEqual(telegram.link_code("beto"), telegram.link_code("carla"))

    def test_sin_enlazar_no_se_manda_nada_y_el_aviso_se_guarda_igual(self):
        self.assertEqual(self.notify_beto().status_code, 201)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.http.get("/api/notifications", headers=self.as_user("beto")).get_json()["unread"], 1)

    def test_desenlazar_deja_de_mandar(self):
        beto = self.as_user("beto")
        self.updates.append(self.start_message("beto", 555))
        self.http.post("/api/notifications/telegram", headers=beto)
        self.assertFalse(self.http.delete("/api/notifications/telegram", headers=beto).get_json()["linked"])
        self.sent.clear()
        self.notify_beto()
        self.assertEqual(self.sent, [])

    def test_la_alerta_cumplida_del_cliente_tambien_llega(self):
        self.updates.append(self.start_message("beto", 555))
        self.http.post("/api/notifications/telegram", headers=self.as_user("beto"))
        alerts.create("beto", {"username": "beto", "role": "usuario"}, "AAPL", "loss", 5)
        alerts.evaluate("beto", losing_view("beto"))  # AAPL va -10%
        self.assertIn("Alerta cumplida: AAPL", self.sent[-1][1])

    def test_sin_token_no_hay_telegram(self):
        beto = self.as_user("beto")
        with mock.patch.object(Config, "TELEGRAM_TOKEN", ""):
            self.assertEqual(self.http.get("/api/notifications/telegram", headers=beto).get_json(),
                             {"available": False, "linked": False, "url": None})
            self.assertEqual(self.http.post("/api/notifications/telegram", headers=beto).status_code, 503)

    def test_el_consultor_no_tiene_bandeja_ni_telegram(self):
        self.assertEqual(self.http.get("/api/notifications/telegram", headers=self.as_user("ana")).status_code, 403)

    def test_un_fallo_de_telegram_no_deja_el_token_en_el_log(self):
        with mock.patch.object(telegram, "_call", telegram_real_call), \
                mock.patch.object(telegram.requests, "post", side_effect=telegram.requests.ConnectionError("https://api.telegram.org/bot123:token-de-prueba/x")), \
                self.assertLogs(telegram.log, "ERROR") as logs:
            self.assertIsNone(telegram._call("getMe"))
        self.assertNotIn("token-de-prueba", "".join(logs.output))


if __name__ == "__main__":
    unittest.main()
