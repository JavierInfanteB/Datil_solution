-- 060: datos iniciales (catálogos). Los usuarios y el historial vienen de la migración de los JSON.
SET search_path TO datil, public;

INSERT INTO puestos (nombre, descripcion, permisos) VALUES
    ('Inversionista', 'Cliente que compra, vende y ve su cartera', ARRAY['portfolio','trading','risk','avisos','plan']),
    ('Consultor',     'Analiza las inversiones de sus clientes',   ARRAY['consultor'])
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO series_mercado (fuente, codigo, nombre, frecuencia, moneda) VALUES
    ('banxico', 'SF43936', 'CETES 28 días - tasa de rendimiento de la subasta',  'semanal', NULL),
    ('banxico', 'SF43939', 'CETES 91 días - tasa de rendimiento de la subasta',  'semanal', NULL),
    ('banxico', 'SF43942', 'CETES 182 días - tasa de rendimiento de la subasta', 'semanal', NULL),
    ('banxico', 'SF43945', 'CETES 364 días - tasa de rendimiento de la subasta', 'semanal', NULL),
    ('banxico', 'SF44071', 'Bono M tasa fija 10 años - tasa de rendimiento de la subasta', 'semanal', NULL)
ON CONFLICT (fuente, codigo) DO NOTHING;

INSERT INTO instrumentos (simbolo, nombre, tipo, tipo_tasa, valor_nominal, moneda_base, plazo_dias, dias_cupon, serie_subasta_id)
SELECT v.simbolo, v.nombre, v.tipo, v.tipo_tasa, v.nominal, 'MXN', v.plazo, v.dias_cupon,
       (SELECT id FROM series_mercado WHERE fuente = 'banxico' AND codigo = v.serie)
FROM (VALUES
    ('CETES28',  'CETES 28 días',              'cetes',  'cero', 10,  28,   NULL::INT, 'SF43936'),
    ('CETES91',  'CETES 91 días',              'cetes',  'cero', 10,  91,   NULL,      'SF43939'),
    ('CETES182', 'CETES 182 días',             'cetes',  'cero', 10,  182,  NULL,      'SF43942'),
    ('CETES364', 'CETES 364 días',             'cetes',  'cero', 10,  364,  NULL,      'SF43945'),
    ('BONOM10',  'Bono M tasa fija 10 años',   'bono_m', 'fija', 100, 3640, 182,       'SF44071')
) AS v(simbolo, nombre, tipo, tipo_tasa, nominal, plazo, dias_cupon, serie)
ON CONFLICT (simbolo) DO NOTHING;

-- Días inhábiles bancarios 2026 (Banxico). Falta cargar otros años cuando se publiquen.
INSERT INTO dias_inhabiles (fecha, descripcion) VALUES
    ('2026-01-01', 'Año Nuevo'), ('2026-02-02', 'Día de la Constitución'), ('2026-03-16', 'Natalicio de Benito Juárez'),
    ('2026-04-02', 'Jueves Santo'), ('2026-04-03', 'Viernes Santo'), ('2026-05-01', 'Día del Trabajo'),
    ('2026-09-16', 'Independencia de México'), ('2026-11-02', 'Día de Muertos'),
    ('2026-11-16', 'Revolución Mexicana'), ('2026-12-25', 'Navidad')
ON CONFLICT (fecha) DO NOTHING;
