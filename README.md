# Dátil Solution

Frontend React + Vite (`frontend/`), API Flask (`backend/`) y **PostgreSQL 16** (`database/`). Los datos viven en PostgreSQL; los JSON de origen y el importador viven en la rama `pruebas`.

## Arranque con Docker (PowerShell, Windows 11 + Docker Desktop)

```powershell
# 1) Configuración (los secretos NO se suben a Git)
Copy-Item .env.example .env
notepad .env        # cambia POSTGRES_PASSWORD, DATIL_APP_PASSWORD, DATIL_READONLY_PASSWORD y SECRET_KEY

# 2) Comprueba que el puerto 8002 esté libre (no debe imprimir nada)
Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue

# 3) Levanta solo este proyecto (no toca tus otros contenedores)
docker compose up -d --build
docker compose ps
docker compose logs migrate     # esquema aplicado + importación de JSON + [AVISO]s
```

Servicios: `db` (postgres:16, puerto **8002** en el host y dentro de Docker), `migrate` (una vez, termina solo), `api` (host **5005**). Todo se publica solo en `127.0.0.1`.

Frontend en desarrollo (otra terminal):

```powershell
cd frontend; npm install; npm run dev     # http://localhost:5173  (llama a http://localhost:5000; para esta API define `VITE_API_URL=http://localhost:5005`)
```

Usuarios de prueba (datos migrados): `usuario`, `consultor`, `admin` con las contraseñas del proyecto original.

## Verificar que PostgreSQL realmente guarda los datos

```powershell
curl.exe http://localhost:5005/api/health        # {"database":"up","status":"ok"}
docker compose exec db psql -U datil_owner -d datil_db -c "\dt datil.*"
docker compose exec db psql -U datil_owner -d datil_db -c "SELECT usuario, rol, efectivo_mxn FROM datil.usuarios;"
docker compose exec db psql -U datil_owner -d datil_db -c "SELECT * FROM datil.v_conciliacion_efectivo;"   # diferencia = 0
Get-Content database\tests\validar_base.sql | docker compose exec -T db psql -U datil_owner -d datil_db -v ON_ERROR_STOP=1

# Persistencia: haz una compra desde la web, reinicia y confirma que sigue ahí
docker compose restart db api
docker compose exec db psql -U datil_owner -d datil_db -c "SELECT count(*) FROM datil.transacciones;"
```

Conéctate con DBeaver/pgAdmin a `localhost:8002`, base `datil_db`, usuario `datil_owner`.

## Riesgo del portafolio

Cuatro lecturas distintas, todas de **riesgo** (Datil no muestra ganancias esperadas ni predice precios):

| Lectura | Qué dice | Cómo se calcula |
|---|---|---|
| Puntaje 0 a 100 (bajo, medio, alto) | Qué tan probable es una mala experiencia en 12 meses | 4 señales históricas: volatilidad, pérdida en los peores días, caída máxima y beta (`backend/utils/risk_engine.py`) |
| **VaR** a 1 mes (95%) | La pérdida de un mes que no se superó en 95 de cada 100 meses del historial, en pesos | Simulación histórica de los últimos 3 años de la mezcla de hoy, con cada mes reescalado por la volatilidad de hoy (Hull-White, EWMA 0.94) |
| **CVaR** a 1 mes (95%) | El promedio de los meses peores que el VaR | Misma simulación |
| **Pérdida estresada** | Lo que perdería la cartera si el mercado global repitiera su peor mes desde 2008 (-35.8%, sep-oct 2008) | Beta del portafolio × el peor mes del ACWI (diario desde 2008) |

Todo sale de `GET /api/risk/portfolio`. Son descripciones del pasado: no son una predicción ni un límite de pérdida.

**Quién ve qué.** El **consultor** (y el admin) ve el detalle completo: puntaje, historial, VaR, CVaR, pérdida estresada, escenarios y concentración. El **cliente** solo ve si el riesgo de su portafolio es **bajo, medio o alto**; el servidor no le manda el detalle (no es solo ocultarlo en la pantalla).

**Qué tan bien responde** (backtest con 59 acciones y 150 carteras de 5; los scripts viven en la rama `pruebas`, `backend/scripts/`):

- VaR 95% a 1 mes: 5.6% de excedencias en acciones sueltas y 4.7% en carteras (esperado 5%); en el mercado bajista de 2022 bajó de 9% a 5% al reescalar por volatilidad.
- Ningún VaR de 3 años ve venir el primer mes de un crash (2020: 27% a 34% de excedencias). Para eso está la pérdida estresada: en el crash de 2020 cubre el 96.5% de las carteras de 5 (3.5% de excedencias). En acciones sueltas falla más (9.3%), porque una empresa puede caer más que el mercado por algo suyo.
- La pérdida estresada ignora el tipo de cambio (en crisis el peso suele debilitarse y amortigua la pérdida de lo extranjero) y el riesgo propio de cada empresa.

## Pruebas automáticas

`main` solo lleva código funcional: las pruebas (`backend/tests`, `database/tests`, `frontend/src/**/*.test.js`) viven en la rama `pruebas` (`git switch pruebas`). Ahí corren así:

Necesitan una base **desechable** (se borra su esquema `datil`). Con el contenedor `db` arriba:

```powershell
docker compose exec db psql -U datil_owner -d postgres -c "CREATE DATABASE datil_test"
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
$env:TEST_DB_NAME="datil_test"; $env:TEST_DB_HOST="localhost"; $env:TEST_DB_PORT="8002"
$env:POSTGRES_USER="datil_owner"; $env:POSTGRES_PASSWORD="<tu POSTGRES_PASSWORD>"
python -m unittest discover -s tests -v
```

## Operación segura
- **No** uses `docker compose down -v` (borra el volumen `datil-solution_pgdata` con todos los datos). Para detener: `docker compose stop` o `docker compose down` (sin `-v`).
- La migración es repetible: `docker compose run --rm migrate` no duplica datos.
- Más detalle (diseño, matriz JSON↔tablas, pendientes): [`docs/REPORTE_CAMBIOS_BASE_DE_DATOS.md`](docs/REPORTE_CAMBIOS_BASE_DE_DATOS.md).
