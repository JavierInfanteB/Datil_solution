# Dátil Solution — Migración a PostgreSQL 16: diagnóstico, matriz y reporte de cambios

Rama sugerida: `feature/postgresql` (no se tocó `main`, no se hizo push).

## 1. Diagnóstico (estado original)

| Aspecto | Hallazgo |
|---|---|
| Almacenamiento | 7 JSON en `data/` (`users`, `portfolios`, `transactions`, `orders`, `notifications`, `permissions`, `assets`) leídos/escritos completos por `utils/data_store.py` con un lock de proceso. |
| Concurrencia | Un solo worker de gunicorn; el lock solo protege dentro del proceso. Dos procesos podrían pisarse el archivo. |
| Sesiones | Diccionario en memoria (`jti → última actividad`): se pierden al reiniciar y no escalan a varios workers. |
| Dinero | `float` de Python en JSON (efectivo, precios, totales). Riesgo de errores de redondeo acumulados. |
| Integridad | Sin claves foráneas ni CHECK: nada impedía efectivo negativo, órdenes huérfanas ni transacciones duplicadas. |
| Auditoría | `audit.json` y bitácora editables; el historial no era inmutable. |
| Datos | `admin` tiene una cartera (efectivo $8,978.61, 5 posiciones) y una orden; el modelo E-R exige que solo `usuario` tenga cartera. |
| Modelo E-R | El documento define 27 tablas; el código no tenía correspondencia con casi ninguna (metas, alertas, sugerencias, emisiones, subastas, asignaciones, sesiones, auditoría…). |

Problemas **previos** a la migración (no introducidos por ella): cartera del admin; sesiones en memoria; floats para dinero; sin integridad referencial; historial editable; `purchase_price` ausente en algunas transacciones antiguas.

## 2. Matriz de correspondencia (JSON ↔ backend ↔ PostgreSQL)

| JSON / estructura | Módulo backend (antes → ahora) | Tabla(s) PostgreSQL | Notas / diferencias |
|---|---|---|---|
| `users.json` (id, username, name, role, password_hash, puesto, consultant, disabled/deleted) | `utils/accounts.py` → `db/accounts.py` | `usuarios`, `puestos`, `asignaciones_consultor` | `disabled/deleted` ↔ `estado` activo/suspendido/baja. El consultor pasa a una asignación vigente (`hasta IS NULL`). El hash de Werkzeug se conserva tal cual. |
| `permissions.json` | `modules/permissions.py` | `usuarios.permisos TEXT[]`, `puestos.permisos` | |
| puestos (default en código) | `DEFAULT_PUESTOS` | `puestos` (seed en `060`) | |
| sesiones en memoria | `auth/jwt_handler.py` | `sesiones` (jti, IP, dispositivo, última actividad) | Sobreviven reinicios. |
| intentos de login | — (no existía) | `intentos_login` | Nuevo. |
| `portfolios.json` `cash` | `utils/stock_engine.py`, `bond_engine.py` | `usuarios.efectivo_mxn` + `movimientos_efectivo` | El saldo solo cambia por trigger al insertar un movimiento (libro de efectivo). |
| `portfolios.json` holdings `accion` | idem | `posiciones_accion`, `acciones_catalogo` | |
| `portfolios.json` holdings `bono` (lotes) | idem | `lotes_bono`, `emisiones`, `instrumentos` | `emisiones` sintéticas con clave `SIMBOLO-AAAAMMDD`. |
| `assets.json` | `utils/market_data.py` | `instrumentos`, `series_mercado`, `datos_mercado` | |
| `orders.json` | `utils/bond_engine.py` | `ordenes_bono`, `subastas` | Subasta martes, colocación jueves (+2 días). Solo órdenes por monto (las antiguas por títulos no caben en el modelo y se reportan). |
| `transactions.json` | `modules/trading.py`, `activity.py` | `transacciones` + `movimientos_efectivo` | Cupones y vencimientos van solo al libro de efectivo. |
| `notifications.json` | `modules/notifications.py` | `avisos`, `envios_aviso` | |
| metas / notas / alertas / sugerencias | `modules/plan.py`, `utils/alerts.py`, `signals.py` | `metas`, `notas`, `alertas`, `eventos_alerta`, `preferencias_alerta`, `sugerencias` | JSON opcionales: se importan si existen. |
| auditoría de admin | `utils/audit.py` | `auditoria_general` | Inmutable. |
| fechas inhábiles | código | `dias_inhabiles` | Seed. |
| historial de patrimonio | — | `historial_patrimonio` | Estructura lista (el E-R la define). |

### Diferencias deliberadas respecto al Modelo E-R (marcadas con "DESVIACIÓN" en el SQL)
- Columnas `uid UUID` en tablas expuestas por la API (los ids públicos del frontend son texto/UUID).
- `tipo_cambio NUMERIC(18,8)`, `tasa NUMERIC(10,6)`, `emisiones.clave VARCHAR(40)`.
- `movimientos_efectivo` añade `cantidad`, `tasa`, `utilidad_realizada_mxn` y `cupones_pagados` en lotes (el frontend los muestra).
- `origen` de transacción incluye `orden_programada` (lo usa `ActivityFeed.jsx`).

## 3. Diseño de la base (`database/`)
- `schema/001…060` (versionados, se aplican una sola vez; checksum en `schema_migraciones`) y `R__seguridad_permisos.sql` (repetible).
- Dinero en `NUMERIC(18,2)`; fechas en `timestamptz`; `CHECK` de signos, estados y cantidades; índices únicos parciales (un vencimiento por lote, un cupón por lote y fecha, una orden de reinversión viva por lote, un consultor vigente por cliente).
- **Libro de efectivo**: `usuarios.efectivo_mxn` **no se actualiza a mano**: el rol `datil_app` no tiene `UPDATE` sobre esa columna; un trigger `SECURITY DEFINER` lo ajusta al insertar en `movimientos_efectivo`. Un `CHECK ≥ 0` aborta cualquier sobregiro. Vista `v_conciliacion_efectivo` verifica saldo = suma de movimientos.
- `transacciones`, `movimientos_efectivo` y `auditoria_general` son **inmutables** (trigger + sin `UPDATE/DELETE` para la app).
- Roles: `datil_app` (DML mínimo) y `datil_readonly`; contraseñas por variables de entorno, nunca en el repo.

## 4. Integración con Flask
- `backend/db/` (conexión psycopg 3, `accounts.py`, `portfolio.py`). Misma forma de respuesta JSON que antes (floats/ints, fechas ISO), mismos endpoints, mismo JWT y roles.
- Los motores (`stock_engine`, `bond_engine`, `bond_math`) siguen siendo funciones puras sobre un dict de cartera: **no cambió su lógica**.
- `portfolio_tx(usuario)`: abre UNA transacción, bloquea la fila del cliente (`SELECT … FOR UPDATE`), calcula con el motor, escribe solo las diferencias y verifica efectivo BD == efectivo del motor; todo o nada. Esto evita compras/ventas/cupones/reinversiones duplicados con peticiones simultáneas.
- Errores de conexión → `DatabaseUnavailable` / `/api/health` responde 503.
- Eliminados `utils/data_store.py` y `utils/seed.py` (ya no hay JSON como almacenamiento).
- Corrección: `sub` del JWT ahora es texto (PyJWT ≥ 2.10 rechaza enteros); funciona también con 2.9.0.

## 5. Migración de JSON (`database/migration/`)
`run_migrations.py` aplica el esquema y, con `--import-json`, ejecuta `import_json.py`:
conserva ids, hashes, importes, fechas y relaciones; es **idempotente** (ids/uuid determinísticos, `ON CONFLICT DO NOTHING`); corre en **una transacción** y falla si saldo ≠ suma de movimientos; **no modifica los JSON** (en Docker se montan `:ro`). Reporta inconsistencias como `[AVISO]`:
- la cartera/orden del admin se omite (el modelo exige rol `usuario`; sigue en el JSON de respaldo);
- se crea un depósito inicial para que `efectivo = Σ movimientos`; si el historial no cuadra con el efectivo del JSON se registra un retiro de conciliación y se avisa;
- órdenes por títulos, referencias a usuarios inexistentes, hashes sin formato Werkzeug, etc.

Resultado real con los datos del repo: 3 usuarios, 1 asignación, 5 posiciones, 8 transacciones, 3 avisos importados; segunda corrida: todo "ya existía"; saldo de `usuario` $73,704.89 = al JSON.

## 6. Pruebas (resultados reales, PostgreSQL 16 local)
`TEST_DB_NAME=… python -m unittest discover -s tests` desde `backend/`: **73 pruebas, OK** (38 de API portadas de JSON a PostgreSQL, 14 de lógica pura, 21 de integración nuevas: esquema/FK/CHECK, importación idempotente, JSON intactos, login/roles, permisos del rol de la app, compra/venta de acciones, fondos insuficientes, rollback, compras simultáneas, sobregiro, admin en nombre de cliente, formas de respuesta del frontend, `/api/health`). Además `database/tests/validar_base.sql` (10 validaciones SQL sobre la base migrada): OK.

### Qué NO se pudo verificar aquí (pendiente, ver README §Verificación)
- `docker compose up -d --build` **no se ejecutó**: el entorno de trabajo no tiene daemon de Docker. La verificación en tu Docker Desktop está pendiente.
- Persistencia tras reiniciar el contenedor y la comprobación del puerto 5434 libre: pendientes en tu máquina.
- Las pruebas usaron un shim de `psycopg` sobre libpq (sin acceso a PyPI); el código usa psycopg 3.2.3 oficial. Primera ejecución real con la librería oficial: pendiente.
- Frontend (React) no se ejecutó; solo se verificó la forma de las respuestas de la API.

## 7. Aviso sobre el despliegue existente (`.github/workflows/deploy.yml`)
Un push a `main` que toque `backend/**` reconstruye y recrea el contenedor en el runner. Con estos cambios la API **necesita PostgreSQL** (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`…). **No hagas merge a `main` hasta configurar la base en el entorno de despliegue**; no se modificó `.github/`. La imagen por defecto (`docker build .`) sigue siendo web+API (`target: full`).

## 8. Archivos
**Nuevos:** `database/**`, `backend/db/**`, `backend/tests/pgfixture.py`, `backend/tests/test_postgres_integration.py`, `docker-compose.yml`, `.env.example`, `README.md`, este reporte.
**Modificados:** `backend/{app,config,requirements.txt}`, `auth/*`, `utils/{accounts,audit,records,notifications,alerts,signals,bond_engine,market_data,stock_engine,decorators}.py`, `modules/*` (acceso a datos), `scripts/check_banxico.py`, `backend/tests/test_accounts_api.py`, `Dockerfile`, `.dockerignore`, `.gitignore`.
**Eliminados (justificado):** `utils/data_store.py`, `utils/seed.py` (almacenamiento JSON). Los `data/*.json` **se conservan** como respaldo.
