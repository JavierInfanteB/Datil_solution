import { idiomaActual } from "../i18n/idioma.js";
// Variación de un activo por periodo (día, quincena, mes, semestre, año) dentro de un lapso.
// Todo el cálculo vive aquí; la pantalla solo lo muestra. Las fechas son "YYYY-MM-DD" y se
// comparan como texto. Los puntos son [{ date, close }] ordenados de más antiguo a más reciente.
//
// Reglas:
// - El lapso va de `from` a la última fecha. Su base es el último cierre en `from` o antes.
// - La variación de un periodo es su último cierre contra el último cierre del periodo anterior
//   (el primero, contra la base del lapso), así los periodos encadenan sin huecos.
// - Quincenas: días 1-15 y 16-fin de mes. Semestres y años son naturales (ene-jun, jul-dic).
// - partialStart: el periodo empezó antes de la base, solo cuenta desde ahí.
//   partialEnd: el periodo aún no termina a la fecha de hoy.

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const monthName = (m) => (idiomaActual() === "en" ? MONTHS_EN : MONTHS)[m - 1];

const pad = (n) => String(n).padStart(2, "0");
const iso = (y, m, d) => `${y}-${pad(m)}-${pad(d)}`;
const parse = (date) => date.split("-").map(Number); // [año, mes 1-12, día]
const daysInMonth = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();

export const todayISO = () => {
  const now = new Date();
  return iso(now.getFullYear(), now.getMonth() + 1, now.getDate());
};

export const addDays = (date, n) => {
  const [y, m, d] = parse(date);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
};

// Si el día no existe en el mes destino (31 de marzo menos un mes), cae en el último día de ese mes.
export const addMonths = (date, n) => {
  const [y, m, d] = parse(date);
  const total = y * 12 + (m - 1) + n;
  const year = Math.floor(total / 12);
  const month = (total % 12) + 1;
  return iso(year, month, Math.min(d, daysInMonth(year, month)));
};

const BUCKETS = {
  dia: (y, m, d) => ({ start: iso(y, m, d), end: iso(y, m, d), label: `${d} ${monthName(m)} ${y}` }),
  quincena: (y, m, d) => {
    const first = d <= 15;
    const last = daysInMonth(y, m);
    return {
      start: iso(y, m, first ? 1 : 16),
      end: iso(y, m, first ? 15 : last),
      label: `${first ? "1-15" : `16-${last}`} ${monthName(m)} ${y}`,
    };
  },
  mes: (y, m) => ({ start: iso(y, m, 1), end: iso(y, m, daysInMonth(y, m)), label: `${monthName(m)} ${y}` }),
  semestre: (y, m) => {
    const second = m > 6;
    return {
      start: iso(y, second ? 7 : 1, 1),
      end: second ? iso(y, 12, 31) : iso(y, 6, 30),
      label: `${idiomaActual() === "en" ? (second ? "Jul-Dec" : "Jan-Jun") : second ? "jul-dic" : "ene-jun"} ${y}`,
    };
  },
  anio: (y) => ({ start: iso(y, 1, 1), end: iso(y, 12, 31), label: String(y) }),
};

export const GRAIN_LABELS = { dia: "Por día", quincena: "Por quincena", mes: "Por mes", semestre: "Por semestre", anio: "Por año" };

// grains: solo las granularidades que tienen sentido para el lapso.
export const LAPSES = [
  { id: "1S", label: "1 semana", days: 7, grains: ["dia"] },
  { id: "1M", label: "1 mes", months: 1, grains: ["dia", "quincena", "mes"] },
  { id: "3M", label: "3 meses", months: 3, grains: ["quincena", "mes"] },
  { id: "6M", label: "6 meses", months: 6, grains: ["quincena", "mes"] },
  { id: "1A", label: "1 año", months: 12, grains: ["mes", "semestre", "anio"] },
];

export const lapseStart = (lastDate, lapse) => (lapse.days ? addDays(lastDate, -lapse.days) : addMonths(lastDate, -lapse.months));

const variation = (open, close) => ({ change: close - open, percent: open ? ((close - open) / open) * 100 : null });

// Puntos del lapso, empezando por la base. Si la historia no llega hasta `from`, la base es el primer punto.
export function sliceLapse(points, from) {
  return points.slice(Math.max(points.findLastIndex((p) => p.date <= from), 0));
}

// Variación de todo el lapso (base contra último cierre), o null si no hay al menos dos puntos.
export function lapseVariation(points, from) {
  const slice = sliceLapse(points, from);
  return slice.length < 2 ? null : variation(slice[0].close, slice.at(-1).close);
}

// Periodos del lapso, de más antiguo a más reciente: { start, end, label, open, close, change, percent, partialStart, partialEnd }.
export function periodVariations(points, grain, { from, today = todayISO() }) {
  const [base, ...rest] = sliceLapse(points, from);
  const rows = [];
  for (const point of rest) {
    const bucket = BUCKETS[grain](...parse(point.date));
    let row = rows.at(-1);
    if (row?.start !== bucket.start) {
      row = { ...bucket, open: row ? row.close : base.close, partialStart: !row && bucket.start <= base.date };
      rows.push(row);
    }
    row.close = point.close;
  }
  return rows.map((row) => ({ ...row, ...variation(row.open, row.close), partialEnd: row.end > today }));
}
