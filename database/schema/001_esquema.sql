-- 001: esquema y control de versiones del esquema.
-- Requiere PostgreSQL 16 (usa UNIQUE NULLS NOT DISTINCT, PG15+, y gen_random_uuid(), PG13+).
-- Se ejecuta como el rol propietario (POSTGRES_USER), nunca como datil_app.
CREATE SCHEMA IF NOT EXISTS datil;
SET search_path TO datil, public;

COMMENT ON SCHEMA datil IS 'Dátil Solution: todas las tablas de la aplicación viven aquí';
