import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { SeverityTag } from "./RiskParts";

const SEVERITIES = ["alta", "media", "baja"];
const COLORS = { alta: "var(--datil-down)", media: "var(--datil-accent)", baja: "var(--datil-text-muted)" };

// Sugerencias de todos los clientes, para leerlas de un vistazo: una gráfica por cliente y prioridad, filtro por
// prioridad y, por cliente, cada sugerencia como "qué hacer" y "por qué". Con muchos clientes solo se abren los
// que más urgencia tienen.
export default function Suggestions({ data, onOpen }) {
  const [filter, setFilter] = useState("alta");
  const [query, setQuery] = useState("");

  const counts = Object.fromEntries(SEVERITIES.map((s) => [s, data.suggestions.filter((x) => x.severity === s).length]));
  const visible = data.suggestions.filter(
    (s) => (filter === "todas" || s.severity === filter) && s.client.toLowerCase().includes(query.trim().toLowerCase())
  );
  const byClient = {};
  for (const s of visible) (byClient[s.username] ??= { client: s.client, items: [] }).items.push(s);
  const groups = Object.entries(byClient).sort(([, a], [, b]) => b.items.length - a.items.length);

  const chart = data.clients
    .filter((c) => data.suggestions.some((s) => s.username === c.username))
    .map((c) => ({
      client: c.client,
      ...Object.fromEntries(SEVERITIES.map((sev) => [sev, data.suggestions.filter((s) => s.username === c.username && s.severity === sev).length])),
    }));

  if (data.suggestions.length === 0) return <p>Ningún cliente tiene alertas por ahora.</p>;

  return (
    <>
      <div className="datil-summary-grid">
        {SEVERITIES.map((s) => (
          <div key={s}>
            <span className="datil-label">Prioridad {s}</span>
            <strong>{counts[s]}</strong>
          </div>
        ))}
      </div>

      <h3 className="datil-subheading">Quién necesita atención</h3>
      <div className="datil-chart-wrapper">
        <ResponsiveContainer width="100%" height={Math.max(160, chart.length * 34)}>
          <BarChart data={chart} layout="vertical" margin={{ left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="client" width={110} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            {SEVERITIES.map((s) => (
              <Bar key={s} dataKey={s} name={`Prioridad ${s}`} stackId="sev" fill={COLORS[s]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h3 className="datil-subheading">Detalle</h3>
      <div className="datil-lapse-bar" role="group" aria-label="Prioridad">
        {["alta", "media", "baja", "todas"].map((s) => (
          <button key={s} className={s === filter ? "datil-chip active" : "datil-chip"} aria-pressed={s === filter} onClick={() => setFilter(s)}>
            {s === "todas" ? "Todas" : `${s[0].toUpperCase()}${s.slice(1)} (${counts[s]})`}
          </button>
        ))}
      </div>
      <label>
        Buscar cliente
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nombre" />
      </label>

      {groups.length === 0 && <p className="datil-period-tag">Sin sugerencias con este filtro.</p>}
      {groups.map(([username, { client, items }], i) => (
        <details key={username} open={i < 3 || query.trim() !== ""}>
          <summary>
            <strong>{client}</strong>
            <span className="datil-period-tag"> {items.length} sugerencia(s)</span>
          </summary>
          <ul className="datil-suggestions">
            {items.map((s, j) => (
              <li key={`${s.id}-${j}`}>
                <SeverityTag severity={s.severity} /> <strong>Qué hacer:</strong> {s.title}
                <div className="datil-period-tag">
                  <strong>Por qué:</strong> {s.detail}
                </div>
              </li>
            ))}
          </ul>
          <button className="datil-link" onClick={() => onOpen(username)}>
            Abrir cliente y avisarle
          </button>
        </details>
      ))}
      <p className="datil-period-tag">
        Son ideas para reducir riesgo con datos históricos; la decisión es tuya y del cliente. No es asesoría financiera.
      </p>
    </>
  );
}
