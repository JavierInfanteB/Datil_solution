-- R__: script repetible (se aplica en cada arranque). Roles y permisos de PostgreSQL.
--   datil_app      : usuario de la aplicación Flask (solo DML; sin DDL; ledger de solo inserción).
--   datil_readonly : consultas y reportes.
-- Las contraseñas llegan por la variable de sesión datil.app_password / datil.readonly_password (nunca viven en el repo).
SET search_path TO datil, public;

DO $$
DECLARE
    pw_app TEXT := current_setting('datil.app_password', true);
    pw_ro  TEXT := current_setting('datil.readonly_password', true);
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'datil_app') THEN
        CREATE ROLE datil_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'datil_readonly') THEN
        CREATE ROLE datil_readonly LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
    IF pw_app IS NOT NULL AND pw_app <> '' THEN
        EXECUTE format('ALTER ROLE datil_app PASSWORD %L', pw_app);
    END IF;
    IF pw_ro IS NOT NULL AND pw_ro <> '' THEN
        EXECUTE format('ALTER ROLE datil_readonly PASSWORD %L', pw_ro);
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO datil_app, datil_readonly', current_database());
END $$;

ALTER ROLE datil_app      SET search_path = datil, public;
ALTER ROLE datil_readonly SET search_path = datil, public;

REVOKE ALL ON SCHEMA datil FROM PUBLIC;
GRANT USAGE ON SCHEMA datil TO datil_app, datil_readonly;

REVOKE ALL ON ALL TABLES IN SCHEMA datil FROM datil_app, datil_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA datil TO datil_app, datil_readonly;

-- La aplicación escribe en las tablas operativas...
GRANT INSERT, UPDATE ON
    puestos, asignaciones_consultor, sesiones, acciones_catalogo, posiciones_accion,
    emisiones, subastas, ordenes_bono, lotes_bono, sugerencias, alertas, avisos, metas, preferencias_alerta,
    envios_aviso, historial_patrimonio, series_mercado
    TO datil_app;
-- usuarios: UPDATE en todas las columnas MENOS efectivo_mxn (el saldo solo cambia por el trigger del libro de efectivo).
GRANT INSERT ON usuarios TO datil_app;
DO $$
BEGIN
    EXECUTE format('GRANT UPDATE (%s) ON usuarios TO datil_app', (
        SELECT string_agg(quote_ident(column_name), ', ') FROM information_schema.columns
        WHERE table_schema = 'datil' AND table_name = 'usuarios' AND column_name <> 'efectivo_mxn'));
END $$;
-- ...borra solo lo que el producto permite borrar (puestos, metas, notas, alertas, posiciones vendidas, preferencias)...
GRANT DELETE ON puestos, metas, notas, alertas, posiciones_accion, preferencias_alerta TO datil_app;
GRANT INSERT, UPDATE ON notas TO datil_app;
GRANT INSERT, UPDATE, DELETE ON datos_mercado TO datil_app;
GRANT INSERT ON eventos_alerta, intentos_login, dias_inhabiles TO datil_app;
-- ...y el libro de efectivo, las transacciones y la auditoría son de SOLO INSERCIÓN (sin UPDATE ni DELETE).
GRANT INSERT ON transacciones, movimientos_efectivo, auditoria_general TO datil_app;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA datil TO datil_app;
-- Los permisos futuros no se heredan solos: este script se vuelve a ejecutar en cada arranque (ver run_migrations.py).
