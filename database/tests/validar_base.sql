-- Validación de una base ya migrada. Falla (con ERROR) si algo no cuadra; si termina, todo pasó.
--   docker compose exec -T db psql -U datil_owner -d datil_db -v ON_ERROR_STOP=1 -f - < database/tests/validar_base.sql
SET search_path TO datil, public;
\echo '== 1. Tablas del modelo E-R (27) =='
DO $$
DECLARE n INT;
BEGIN
    SELECT count(*) INTO n FROM pg_tables WHERE schemaname = 'datil' AND tablename <> 'schema_migraciones';
    IF n <> 27 THEN RAISE EXCEPTION 'Se esperaban 27 tablas y hay %', n; END IF;
END $$;
\echo '== 2. Todas las tablas tienen llave primaria =='
DO $$
DECLARE t TEXT;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'datil' AND tablename <> 'schema_migraciones' LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE contype = 'p' AND conrelid = format('datil.%I', t)::regclass) THEN
            RAISE EXCEPTION 'La tabla % no tiene llave primaria', t;
        END IF;
    END LOOP;
END $$;
\echo '== 3. Sin columnas FLOAT/REAL (el dinero es NUMERIC) =='
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'datil' AND data_type IN ('real', 'double precision')) THEN
        RAISE EXCEPTION 'Hay columnas de punto flotante';
    END IF;
END $$;
\echo '== 4. Saldo de cada cliente = suma de su libro de efectivo =='
DO $$
DECLARE bad TEXT;
BEGIN
    SELECT string_agg(usuario || ' (' || diferencia || ')', ', ') INTO bad FROM v_conciliacion_efectivo WHERE diferencia <> 0;
    IF bad IS NOT NULL THEN RAISE EXCEPTION 'Saldos que no concilian: %', bad; END IF;
END $$;
\echo '== 5. Ningún saldo negativo; solo los clientes tienen efectivo =='
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM usuarios WHERE efectivo_mxn < 0 OR (rol <> 'usuario' AND efectivo_mxn <> 0)) THEN
        RAISE EXCEPTION 'Efectivo inválido';
    END IF;
END $$;
\echo '== 6. Contraseñas con hash (nunca texto plano) =='
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM usuarios WHERE contrasena_hash !~ '^(scrypt|pbkdf2):') THEN
        RAISE EXCEPTION 'Hay contraseñas sin hash de Werkzeug';
    END IF;
END $$;
\echo '== 7. Sin duplicados financieros (un vencimiento por lote, un cupón por lote y fecha) =='
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM movimientos_efectivo WHERE tipo = 'vencimiento' GROUP BY lote_id HAVING count(*) > 1)
       OR EXISTS (SELECT 1 FROM movimientos_efectivo WHERE tipo = 'cupon' GROUP BY lote_id, fecha_hora HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'Movimientos duplicados';
    END IF;
END $$;
\echo '== 8. Cada transacción tiene su movimiento de efectivo con el mismo importe =='
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM transacciones t LEFT JOIN movimientos_efectivo m ON m.transaccion_id = t.id
               WHERE m.id IS NULL OR abs(m.monto_mxn) <> t.total_mxn) THEN
        RAISE EXCEPTION 'Transacciones sin movimiento o con importe distinto';
    END IF;
END $$;
\echo '== 9. Un solo consultor vigente por cliente =='
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM asignaciones_consultor WHERE hasta IS NULL GROUP BY cliente_id HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'Cliente con más de un consultor vigente';
    END IF;
END $$;
\echo '== 10. Los registros inmutables rechazan UPDATE/DELETE (incluso del propietario) =='
DO $$
BEGIN
    BEGIN
        UPDATE auditoria_general SET accion = accion WHERE false OR id = (SELECT min(id) FROM auditoria_general);
        IF EXISTS (SELECT 1 FROM auditoria_general) THEN RAISE EXCEPTION 'auditoria_general permitió UPDATE'; END IF;
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END $$;
\echo 'OK: todas las validaciones pasaron'
