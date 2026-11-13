-- 050: funciones, triggers y vistas que protegen la integridad financiera.
SET search_path TO datil, public;

-- 1) El saldo del cliente (usuarios.efectivo_mxn) solo cambia insertando un movimiento, en la misma transacción.
--    Si el saldo quedara negativo, el CHECK de usuarios aborta todo (compra sin fondos = error, no saldo negativo).
-- SECURITY DEFINER: corre con los privilegios del propietario, porque la aplicación (datil_app) NO tiene UPDATE sobre
-- usuarios.efectivo_mxn: el saldo solo puede cambiar a través de esta función, es decir, insertando un movimiento.
CREATE OR REPLACE FUNCTION fn_aplicar_movimiento_efectivo() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = datil, pg_temp AS $$
BEGIN
    UPDATE usuarios SET efectivo_mxn = efectivo_mxn + NEW.monto_mxn WHERE id = NEW.usuario_id;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_movimiento_aplica_saldo
    AFTER INSERT ON movimientos_efectivo
    FOR EACH ROW EXECUTE FUNCTION fn_aplicar_movimiento_efectivo();

-- 2) Registros inmutables: la bitácora, las transacciones y el libro de efectivo no se editan ni se borran.
CREATE OR REPLACE FUNCTION fn_registro_inmutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es de solo inserción (% no permitido)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE TRIGGER trg_auditoria_inmutable BEFORE UPDATE OR DELETE ON auditoria_general
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();
CREATE TRIGGER trg_transacciones_inmutable BEFORE UPDATE OR DELETE ON transacciones
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();
CREATE TRIGGER trg_movimientos_inmutable BEFORE UPDATE OR DELETE ON movimientos_efectivo
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();

-- 3) Reglas entre tablas que un CHECK no puede expresar: posiciones, lotes, órdenes y movimientos solo de clientes.
CREATE OR REPLACE FUNCTION fn_solo_clientes() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE rol_usuario TEXT;
BEGIN
    SELECT rol INTO rol_usuario FROM usuarios WHERE id = NEW.usuario_id;
    IF rol_usuario IS DISTINCT FROM 'usuario' THEN
        RAISE EXCEPTION 'La tabla % solo admite usuarios con rol "usuario" (id %, rol %)',
            TG_TABLE_NAME, NEW.usuario_id, rol_usuario USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_posiciones_solo_clientes BEFORE INSERT OR UPDATE OF usuario_id ON posiciones_accion
    FOR EACH ROW EXECUTE FUNCTION fn_solo_clientes();
CREATE TRIGGER trg_lotes_solo_clientes BEFORE INSERT OR UPDATE OF usuario_id ON lotes_bono
    FOR EACH ROW EXECUTE FUNCTION fn_solo_clientes();
CREATE TRIGGER trg_ordenes_solo_clientes BEFORE INSERT OR UPDATE OF usuario_id ON ordenes_bono
    FOR EACH ROW EXECUTE FUNCTION fn_solo_clientes();
CREATE TRIGGER trg_movimientos_solo_clientes BEFORE INSERT ON movimientos_efectivo
    FOR EACH ROW EXECUTE FUNCTION fn_solo_clientes();
CREATE TRIGGER trg_transacciones_solo_clientes BEFORE INSERT ON transacciones
    FOR EACH ROW EXECUTE FUNCTION fn_solo_clientes();

CREATE OR REPLACE FUNCTION fn_validar_asignacion() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE rol_cliente TEXT; rol_consultor TEXT;
BEGIN
    SELECT rol INTO rol_cliente FROM usuarios WHERE id = NEW.cliente_id;
    SELECT rol INTO rol_consultor FROM usuarios WHERE id = NEW.consultor_id;
    IF rol_cliente IS DISTINCT FROM 'usuario' OR rol_consultor IS DISTINCT FROM 'consultor' THEN
        RAISE EXCEPTION 'Solo un usuario puede asignarse a un consultor que exista (cliente=%, consultor=%)',
            rol_cliente, rol_consultor USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_asignacion_roles BEFORE INSERT ON asignaciones_consultor
    FOR EACH ROW EXECUTE FUNCTION fn_validar_asignacion();

-- 4) Calendario bancario (los días inhábiles se cargan en dias_inhabiles; el backend aún usa solo lunes a viernes).
CREATE OR REPLACE FUNCTION fn_es_dia_habil(d DATE) RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$
    SELECT EXTRACT(ISODOW FROM d) < 6 AND NOT EXISTS (SELECT 1 FROM dias_inhabiles WHERE fecha = d)
$$;

CREATE OR REPLACE FUNCTION fn_dia_habil_antes(d DATE, n INTEGER) RETURNS DATE
LANGUAGE plpgsql STABLE AS $$
DECLARE dia DATE := d; faltan INTEGER := n;
BEGIN
    WHILE faltan > 0 LOOP
        dia := dia - 1;
        IF fn_es_dia_habil(dia) THEN faltan := faltan - 1; END IF;
    END LOOP;
    RETURN dia;
END $$;

-- 5) Vistas de conciliación y consulta.
CREATE OR REPLACE VIEW v_conciliacion_efectivo AS
SELECT u.id AS usuario_id, u.usuario, u.efectivo_mxn,
       COALESCE(SUM(m.monto_mxn), 0)::NUMERIC(18,2) AS suma_movimientos,
       (u.efectivo_mxn - COALESCE(SUM(m.monto_mxn), 0))::NUMERIC(18,2) AS diferencia
FROM usuarios u LEFT JOIN movimientos_efectivo m ON m.usuario_id = u.id
WHERE u.rol = 'usuario'
GROUP BY u.id, u.usuario, u.efectivo_mxn;

CREATE OR REPLACE VIEW v_cartera_usuario AS
SELECT p.usuario_id, 'accion'::TEXT AS tipo, p.simbolo, p.cantidad, p.costo_base_mxn AS costo_mxn
FROM posiciones_accion p
UNION ALL
SELECT l.usuario_id, 'bono', e.instrumento_id, l.cantidad, ROUND(l.precio_compra * l.cantidad, 2)
FROM lotes_bono l JOIN emisiones e ON e.id = l.emision_id WHERE l.estado = 'vigente';
