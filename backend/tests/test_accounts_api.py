"""Roles, puestos y panel del consultor contra una app de Flask con datos temporales.

Se corre desde backend/:  python -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from routes import register_routes  # noqa: E402
from utils import data_store  # noqa: E402

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
        {"symbol": "AAPL", "name": "Apple", "type": "accion", "gain_percent": 12.5, "gain_mxn": 100.0}]}


def fake_risk(username, view=None):
    return {
        "total": 1000.0, "incomplete": False, "history": None, "scenarios": [],
        "stocks": {"share": 90.0, "level": "alto", "weighted_score": 70.0, "positions": [
            {"symbol": "AAPL", "name": "Apple", "weight": 60.0, "score": 70.0, "level": "alto"}]},
        "concentration": {"cash_share": 10.0, "currency_exposure": {"MXN": 10.0, "USD": 90.0}},
    }


class AccountsApiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(data_store, "DATA_DIR", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

        users = [{**u, "password_hash": PASSWORD_HASH} for u in USERS]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        files = {
            "users.json": {"users": users},
            "permissions.json": {},
            # Sin puestos.json: se usan los puestos de arranque.
            "transactions.json": {"beto": [
                {"id": "t1", "date": now, "type": "accion", "side": "buy", "symbol": "AAPL", "name": "Apple",
                 "quantity": 1, "total_mxn": 500.0},
                {"id": "t2", "date": now, "type": "accion", "side": "sell", "symbol": "AAPL", "name": "Apple",
                 "quantity": 1, "total_mxn": 600.0, "realized_pnl_mxn": 100.0},
            ]},
        }
        for name, content in files.items():
            with open(os.path.join(tmp.name, name), "w", encoding="utf-8") as f:
                json.dump(content, f)

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
        self.assertEqual(set(modules), {"portfolio", "trading", "risk", "avisos"})
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
            self.assertEqual(data["totals"]["alerts"], 2)  # AAPL: concentracion y riesgo alto, ambas de prioridad alta
            self.assertEqual(len(data["activity"]), 7)
            self.assertEqual(data["top_sales"][0]["realized_pnl_mxn"], 100.0)
            self.assertEqual(data["top_positions"][0]["symbol"], "AAPL")
            self.assertEqual(data["suggestions"][0]["id"], "concentration")  # AAPL pesa 60%
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


if __name__ == "__main__":
    unittest.main()
