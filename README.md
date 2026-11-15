# Dátil Solution

Frontend React + Vite (`frontend/`), API Flask (`backend/`) y **PostgreSQL 16** (`database/`). Los `data/*.json` quedan solo como respaldo y origen de la migración inicial.

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
