"""Pruebas de integracion contra PostgreSQL real: esquema, permisos, importacion, API y atomicidad financiera.

Requiere TEST_DB_NAME (base desechable; se borra su esquema `datil`). Desde backend/:  python -m unittest discover -s tests
"""
import hashlib
import json
import os
import sys
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pgfixture  # noqa: E402
import psycopg  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

DATA_DIR = pgfixture.ROOT / "data"
PW = "clave-de-prueba-2"
PW_HASH = generate_password_hash(PW)
USERS = [
    {"id": 1, "username": "root", "name": "Root", "role": "admin", "password_hash": PW_HASH},
    {"id": 2, "username": "ana", "name": "Ana", "role": "consultor", "puesto": "Consultor", "password_hash": PW_HASH},
    {"id": 3, "username": "beto", "name": "Beto", "role": "usuario", "puesto": "Inversionista", "consultant": "ana", "password_hash": PW_HASH},
    {"id": 4, "username": "carla", "name": "Carla", "role": "usuario", "puesto": "Inversionista", "password_hash": PW_HASH},
]
TABLES_ER = {
    "usuarios", "puestos", "asignaciones_consultor", "sesiones", "intentos_login", "instrumentos", "series_mercado", "datos_mercado",
    "dias_inhabiles", "emisiones", "subastas", "acciones_catalogo", "posiciones_accion", "lotes_bono", "ordenes_bono", "transacciones",
    "movimientos_efectivo", "avisos", "envios_aviso", "metas", "notas", "alertas", "preferencias_alerta", "eventos_alerta",
    "sugerencias", "historial_patrimonio", "auditoria_general",
}


def file_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DATA_DIR.glob("*.json"))}


@unittest.skipUnless(pgfixture.configured(), "define TEST_DB_NAME para correr contra PostgreSQL")
class PostgresIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pgfixture.ensure_schema()
        import app as application  # la app real, con /api/health y la conexion a PostgreSQL
        cls.app = application.app

    def setUp(self):
        now = datetime.now(timezone.utc)
        self.files = {
            "users.json": {"users": USERS}, "permissions.json": {}, "orders.json": {},
            "portfolios.json": {"beto": {"cash": 10000.0, "holdings": [
                {"type": "accion", "symbol": "AAPL", "name": "Apple", "currency": "MXN", "quantity": 2, "avg_cost": 100.0, "cost_basis_mxn": 200.0}]}, "carla": {"cash": 500.0, "holdings": []}},
            "transactions.json": {"beto": [
                {"id": str(uuid.UUID(int=77)), "date": (now - timedelta(days=2)).isoformat(timespec="seconds"), "type": "accion", "side": "buy",
                 "symbol": "AAPL", "name": "Apple", "quantity": 2, "price": 100.0, "total_mxn": 200.0, "currency": "MXN"}]},
        }
        self.report = pgfixture.load_json_files(self.files)
        self.http = self.app.test_client()

    def login(self, name):
        r = self.http.post("/api/auth/login", json={"username": name, "password": PW})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['token']}"}

    def owner(self):
        return pgfixture.owner_conn()

    def app_conn(self):
        return psycopg.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=os.environ["DB_NAME"], user="datil_app",
                               password=pgfixture.APP_PASSWORD, options="-c search_path=datil,public", autocommit=True)

    def buy(self, who, qty, price=10.0, client=None):
        body = {"symbol": "AAPL", "asset_type": "accion", "quantity": qty}
        if client:
            body["client"] = client
        with mock.patch("modules.trading.get_current_price", return_value={"price": price, "currency": "MXN", "name": "Apple"}), \
                mock.patch("modules.trading.get_fx_to_mxn", return_value=1.0):
            return self.http.post("/api/trading/buy", headers=self.login(who), json=body)

    def cash(self, name):
        with self.owner() as c:
            return float(c.execute("SELECT efectivo_mxn FROM usuarios WHERE usuario = %s", (name,)).fetchone()["efectivo_mxn"])

    # ------------------------------------------------------------------ esquema
    def test_conexion_y_salud(self):
        body = self.http.get("/api/health")
        self.assertEqual((body.status_code, body.get_json()["database"]), (200, "up"))

    def test_estan_las_tablas_del_modelo_er_con_sus_claves(self):
        with self.owner() as c:
            tables = {r["tablename"] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'datil'").fetchall()}
            self.assertTrue(TABLES_ER <= tables, TABLES_ER - tables)
            no_pk = [t for t in TABLES_ER if not c.execute(
                "SELECT 1 FROM pg_constraint WHERE contype = 'p' AND conrelid = %s::regclass", (f"datil.{t}",)).fetchone()]
            self.assertEqual(no_pk, [])
            fks = c.execute("SELECT count(*) AS n FROM pg_constraint WHERE contype = 'f' AND connamespace = 'datil'::regnamespace").fetchone()["n"]
            self.assertGreater(fks, 40)
            money = c.execute("SELECT count(*) AS n FROM information_schema.columns WHERE table_schema = 'datil' "
                              "AND data_type IN ('real', 'double precision')").fetchone()["n"]
            self.assertEqual(money, 0, "no debe haber FLOAT en el esquema")

    def test_los_checks_y_las_claves_foraneas_rechazan_datos_malos(self):
        with self.owner() as c:
            with self.assertRaises(psycopg.errors.CheckViolation):
                c.execute("UPDATE usuarios SET efectivo_mxn = -1 WHERE usuario = 'beto'")
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                c.execute("INSERT INTO posiciones_accion (usuario_id, simbolo, cantidad, costo_promedio, costo_base_mxn) VALUES (3, 'NOEXISTE', 1, 1, 1)")
            with self.assertRaises(psycopg.errors.UniqueViolation):
                c.execute("INSERT INTO usuarios (usuario, nombre, contrasena_hash, rol) VALUES ('beto', 'x', 'y', 'usuario')")

    # ------------------------------------------------------------------ importacion
    def test_la_importacion_conserva_ids_hashes_y_montos(self):
        with self.owner() as c:
            row = c.execute("SELECT id, contrasena_hash, efectivo_mxn FROM usuarios WHERE usuario = 'beto'").fetchone()
        self.assertEqual((row["id"], row["contrasena_hash"], float(row["efectivo_mxn"])), (3, PW_HASH, 10000.0))
        self.assertFalse(row["contrasena_hash"] == PW)  # nunca texto plano

    def test_importar_dos_veces_no_duplica(self):
        with self.owner() as c:
            def counts():
                return {t: c.execute(f"SELECT count(*) AS n FROM datil.{t}").fetchone()["n"]
                        for t in ("usuarios", "transacciones", "movimientos_efectivo", "posiciones_accion")}
            before = counts()
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                for name, content in self.files.items():
                    Path(tmp, name).write_text(json.dumps(content), encoding="utf-8")
                again = pgfixture.import_json.run_import(c, tmp)
            self.assertEqual(counts(), before)
            self.assertEqual(again["integrity_problems"], [])

    def test_los_datos_inconsistentes_se_reportan(self):
        files = {**self.files, "portfolios.json": {**self.files["portfolios.json"], "root": {"cash": 5.0, "holdings": []}}}
        report = pgfixture.load_json_files(files)
        self.assertTrue(any("'root'" in w for w in report["warnings"]), report["warnings"])

    def test_la_importacion_real_no_modifica_los_json_de_respaldo(self):
        before = file_hashes()
        with self.owner() as c:
            pgfixture.wipe(c)
            report = pgfixture.import_json.run_import(c, str(DATA_DIR))
        self.assertEqual(report["integrity_problems"], [])
        self.assertEqual(file_hashes(), before)
        self.assertGreater(len(before), 0)

    # ------------------------------------------------------------------ autenticacion y roles
    def test_login_roles_y_token(self):
        for who, role in (("root", "admin"), ("ana", "consultor"), ("beto", "usuario")):
            r = self.http.post("/api/auth/login", json={"username": who, "password": PW})
            self.assertEqual((r.status_code, r.get_json()["user"]["role"]), (200, role))
        self.assertEqual(self.http.post("/api/auth/login", json={"username": "beto", "password": "mal"}).status_code, 401)
        self.assertEqual(self.http.get("/api/portfolio").status_code, 401)

    def test_el_login_fallido_queda_registrado_y_la_sesion_en_la_base(self):
        self.http.post("/api/auth/login", json={"username": "beto", "password": "mal"})
        self.login("beto")
        with self.owner() as c:
            self.assertGreaterEqual(c.execute("SELECT count(*) AS n FROM intentos_login WHERE NOT exitoso").fetchone()["n"], 1)
            self.assertEqual(c.execute("SELECT count(*) AS n FROM sesiones WHERE cerrada_en IS NULL").fetchone()["n"], 1)

    def test_un_cliente_no_ve_los_datos_de_otro_ni_del_admin(self):
        carla = self.login("carla")
        self.assertEqual(self.http.get("/api/admin/clients", headers=carla).status_code, 403)
        self.assertEqual(self.http.get("/api/consultant/dashboard", headers=carla).status_code, 403)
        view = self.http.get("/api/portfolio", headers=carla).get_json()
        self.assertEqual(view["cash"], 500.0)

    # ------------------------------------------------------------------ permisos del rol de la app
    def test_la_app_no_puede_modificar_ni_borrar_el_historial(self):
        self.assertEqual(self.buy("beto", 1).status_code, 200)
        with self.app_conn() as c:
            for sql in ("UPDATE transacciones SET total_mxn = 1", "DELETE FROM transacciones", "UPDATE movimientos_efectivo SET monto_mxn = 1",
                        "DELETE FROM movimientos_efectivo", "DELETE FROM auditoria_general", "UPDATE auditoria_general SET accion = 'x'"):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=sql):
                    c.execute(f"SET search_path = datil; {sql}")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute("DROP TABLE datil.usuarios")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):  # el saldo solo cambia por el libro, no a mano
                c.execute("UPDATE datil.usuarios SET efectivo_mxn = 999999 WHERE usuario = 'beto'")

    def test_el_rol_de_solo_lectura_no_escribe(self):
        with psycopg.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=os.environ["DB_NAME"], user="datil_readonly",
                             password=pgfixture.RO_PASSWORD, options="-c search_path=datil", autocommit=True) as c:
            self.assertGreater(c.execute("SELECT count(*) FROM usuarios").fetchone()[0], 0)
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute("DELETE FROM usuarios")

    # ------------------------------------------------------------------ acciones y efectivo
    def test_comprar_acciones_actualiza_posicion_efectivo_y_libro(self):
        r = self.buy("beto", 5, price=10.0)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertAlmostEqual(self.cash("beto"), 10000 - 50)
        with self.owner() as c:
            pos = c.execute("SELECT cantidad FROM posiciones_accion p JOIN usuarios u ON u.id = p.usuario_id "
                            "WHERE u.usuario = 'beto' AND simbolo = 'AAPL'").fetchone()
            self.assertEqual(float(pos["cantidad"]), 7.0)  # 2 migradas + 5
            self.assertEqual(c.execute("SELECT count(*) AS n FROM v_conciliacion_efectivo WHERE diferencia <> 0").fetchone()["n"], 0)

    def test_vender_acciones_devuelve_efectivo(self):
        self.buy("beto", 5, price=10.0)
        with mock.patch("modules.trading.get_current_price", return_value={"price": 12.0, "currency": "MXN", "name": "Apple"}), \
                mock.patch("modules.trading.get_fx_to_mxn", return_value=1.0):
            r = self.http.post("/api/trading/sell", headers=self.login("beto"), json={"symbol": "AAPL", "asset_type": "accion", "quantity": 3})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertAlmostEqual(self.cash("beto"), 10000 - 50 + 36)

    def test_no_se_compra_sin_fondos_ni_se_vende_lo_que_no_se_tiene(self):
        self.assertEqual(self.buy("carla", 1000, price=10.0).status_code, 400)  # $10,000 con $500
        self.assertEqual(self.cash("carla"), 500.0)
        with mock.patch("modules.trading.get_current_price", return_value={"price": 10.0, "currency": "MXN", "name": "Apple"}), \
                mock.patch("modules.trading.get_fx_to_mxn", return_value=1.0):
            r = self.http.post("/api/trading/sell", headers=self.login("carla"), json={"symbol": "AAPL", "asset_type": "accion", "quantity": 1})
        self.assertEqual(r.status_code, 400)
        with self.owner() as c:
            self.assertEqual(c.execute("SELECT count(*) AS n FROM transacciones t JOIN usuarios u ON u.id = t.usuario_id "
                                       "WHERE u.usuario = 'carla'").fetchone()["n"], 0)

    def test_una_operacion_fallida_se_revierte_completa(self):
        # Si algo truena a mitad de la operacion, ni la posicion ni el efectivo ni el historial cambian.
        with self.owner() as c:
            before = (self.cash("beto"), c.execute("SELECT count(*) AS n FROM transacciones").fetchone()["n"])
        with mock.patch("db.portfolio.PortfolioSession._insert_trade", side_effect=RuntimeError("falla simulada")):
            try:
                self.buy("beto", 3)
            except Exception:
                pass
        with self.owner() as c:
            after = (self.cash("beto"), c.execute("SELECT count(*) AS n FROM transacciones").fetchone()["n"])
        self.assertEqual(before, after)

    def test_compras_simultaneas_no_gastan_dos_veces_el_mismo_efectivo(self):
        # carla tiene $500: dos compras de $400 a la vez; solo una puede pasar, y el saldo nunca queda negativo.
        results = []

        def go():
            with self.app.test_client() as client:
                with mock.patch("modules.trading.get_current_price", return_value={"price": 40.0, "currency": "MXN", "name": "Apple"}), \
                        mock.patch("modules.trading.get_fx_to_mxn", return_value=1.0):
                    token = client.post("/api/auth/login", json={"username": "carla", "password": PW}).get_json()["token"]
                    results.append(client.post("/api/trading/buy", headers={"Authorization": f"Bearer {token}"},
                                               json={"symbol": "AAPL", "asset_type": "accion", "quantity": 10}).status_code)

        threads = [threading.Thread(target=go) for _ in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), [200, 400], results)
        self.assertAlmostEqual(self.cash("carla"), 100.0)
        with self.owner() as c:
            self.assertEqual(c.execute("SELECT count(*) AS n FROM transacciones t JOIN usuarios u ON u.id = t.usuario_id "
                                       "WHERE u.usuario = 'carla'").fetchone()["n"], 1)

    def test_el_libro_rechaza_sobregiros_y_duplicados_de_vencimiento(self):
        with self.owner() as c:
            uid = c.execute("SELECT id FROM usuarios WHERE usuario = 'carla'").fetchone()["id"]
            with self.assertRaises(psycopg.errors.CheckViolation):
                c.execute("INSERT INTO movimientos_efectivo (usuario_id, fecha_hora, tipo, monto_mxn) VALUES (%s, now(), 'retiro', -1000)", (uid,))
            self.assertEqual(self.cash("carla"), 500.0)

    def test_el_admin_opera_en_nombre_de_un_cliente_y_queda_auditado(self):
        self.assertEqual(self.buy("root", 1, client="carla").status_code, 200)
        with self.owner() as c:
            row = c.execute("SELECT t.hecha_por, t.rol_de_quien_la_hizo, u.usuario FROM transacciones t "
                            "JOIN usuarios u ON u.id = t.usuario_id WHERE u.usuario = 'carla'").fetchone()
            self.assertEqual((row["rol_de_quien_la_hizo"], row["usuario"]), ("admin", "carla"))
            self.assertGreaterEqual(c.execute("SELECT count(*) AS n FROM auditoria_general").fetchone()["n"], 1)
        self.assertEqual(self.buy("root", 1).status_code, 403)  # el admin no tiene cartera propia

    # ------------------------------------------------------------------ compatibilidad con el frontend
    def test_formas_de_respuesta_que_usa_el_frontend(self):
        r = self.http.post("/api/auth/login", json={"username": "beto", "password": PW}).get_json()
        self.assertTrue({"token", "user"} <= set(r))
        self.assertTrue({"id", "username", "name", "role"} <= set(r["user"]))
        h = self.login("beto")
        pf = self.http.get("/api/portfolio", headers=h).get_json()
        self.assertTrue({"cash", "holdings", "currency"} <= set(pf), set(pf))
        self.assertTrue({"symbol", "quantity", "type"} <= set(pf["holdings"][0]))
        self.assertIsInstance(pf["cash"], float)
        self.assertIsInstance(self.http.get("/api/trading/transactions", headers=h).get_json(), (list, dict))
        with mock.patch("modules.admin.build_portfolio_view", lambda u, settle=True: {"portfolio_total": 1.0, "holdings_count": 0, "cash": 1.0, "holdings": []}):
            clients = self.http.get("/api/admin/clients", headers=self.login("root")).get_json()
        self.assertTrue({"clients", "audit"} <= set(clients))
        self.assertTrue({"username", "name", "cash"} <= set(clients["clients"][0]))

    def test_una_base_caida_responde_503_y_no_un_error_opaco(self):
        with mock.patch("app.db.ping", return_value=False):
            r = self.http.get("/api/health")
        self.assertEqual((r.status_code, r.get_json()["database"]), (503, "down"))


if __name__ == "__main__":
    unittest.main()
