import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatCurrency } from "../utils/format";

const COLORS = ["#c9971f", "#3b6ea5", "#2f855a", "#8b5cf6", "#d9480f", "#0e7490", "#be185d", "#9ca3af"];
const MAX_SLICES = 7;

// Suma el valor por nombre y agrupa lo más chico en "Otros" para que el pastel se lea.
export function slices(entries) {
  const totals = {};
  for (const { name, value } of entries) if (value > 0) totals[name] = (totals[name] ?? 0) + value;
  const sorted = Object.entries(totals)
    .map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }))
    .sort((a, b) => b.value - a.value);
  if (sorted.length <= MAX_SLICES + 1) return sorted;
  const rest = sorted.slice(MAX_SLICES).reduce((n, s) => n + s.value, 0);
  return [...sorted.slice(0, MAX_SLICES), { name: "Otros", value: Math.round(rest * 100) / 100 }];
}

// Lo que hay en carteras (acciones, bonos y efectivo) a partir de filas con `holdings` [{symbol, value}] y `cash`.
export const holdingEntries = (rows) =>
  rows.flatMap((r) => [...r.holdings.map((h) => ({ name: h.symbol, value: h.value })), { name: "Efectivo", value: r.cash }]);

// Gráfica de pastel con título y total; `data` ya viene como [{name, value}] (ver slices).
export default function CompositionPie({ title, data }) {
  const total = data.reduce((n, s) => n + s.value, 0);
  return (
    <section className="datil-card">
      <h2>{title}</h2>
      {data.length === 0 ? (
        <p className="datil-period-tag">Sin datos que repartir.</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                {data.map((s, i) => (
                  <Cell key={s.name} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v, name) => [`${formatCurrency(v)} (${((v / total) * 100).toFixed(1)}%)`, name]} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
          <p className="datil-period-tag">Total: {formatCurrency(total)}</p>
        </>
      )}
    </section>
  );
}
