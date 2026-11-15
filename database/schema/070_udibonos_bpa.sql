-- 070: Udibonos y BPA (reglas de Banxico que entraron a main despues del modelo de 27 tablas).
SET search_path TO datil, public;

-- DESVIACIÓN: series adicionales de Banxico que cada instrumento necesita (plazo real de la subasta, CETES y TPFG de
-- referencia, precio limpio, protección a la inflación), con la misma forma que data/assets.json.
-- shortcut: van en un JSONB para no abrir cuatro llaves foráneas más a series_mercado; normalizar si se llegan a consultar por SQL.
ALTER TABLE instrumentos ADD COLUMN series_extra JSONB NOT NULL DEFAULT '{}';

-- Estado del periodo de cupón en curso de un BPA: su tasa (se fija al inicio de cada periodo) y la UDI con que empezó (BPA182).
ALTER TABLE lotes_bono
    ADD COLUMN tasa_vigente       NUMERIC(10,6),
    ADD COLUMN udi_inicio_periodo NUMERIC(12,6);
