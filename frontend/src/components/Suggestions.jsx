import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { apiError } from "../utils/risk";
import { RiskBadge, SeverityTag } from "./RiskParts";

const SEVERITIES = ["alta", "media", "baja"];
const COLORS = { alta: "var(--datil-down)", media: "var(--datil-accent)", baja: "var(--datil-text-muted)" };
const signed = (v) => (v == null ? "N/D" : `${v > 0 ? "+" : ""}${v}%`);

// Sugerencias del consultor ordenadas por acción: cada acción con los clientes que la tienen y qué conviene hacer
// con ella. Lo que no es de una sola acción (escenarios, divisas, diversificación) va aparte, y al final una lista de
// ideas de acciones de riesgo bajo para revisar con los clientes.
export default function Suggestions({ data, onOpen }) {
  const [filter, setFilter] = useState("todas");
  const all = data.suggestions;
  const counts = Object.fromEntries(SEVERITIES.map((s) => [s, all.filter((x) => x.severity === s).length]));
  const visible = all.filter((s) => filter === "todas" || s.severity === filter);

  const bySymbol = {};
  for (const s of visible.filter((x) => x.symbol)) (bySymbol[s.symbol] ??= []).push(s);
  const stocks = Object.entries(bySymbol).sort(([, a], [, b]) => b.length - a.length);
  const general = visible.filter((x) => !x.symbol);

  const chart = data.clients
    .filter((c) => all.some((s) => s.username === c.username))
    .map((c) => ({ client: c.client, ...Object.fromEntries(SEVERITIES.map((sev) => [sev, all.filter((s) => s.username === c.username && s.severity === sev).length])) }));

  return (
    <>
      {all.length === 0 ? (
        <section className="datil-card">
          <h2>Sugerencias por acción</h2>
          <p>Ningún cliente tiene alertas por ahora.</p>
        </section>
      ) : (
        <>
          <div className="datil-grid-2">
            <section className="datil-card">
              <h2>Resumen</h2>
              <div className="datil-summary-grid">
                {SEVERITIES.map((s) => (
                  <div key={s}>
                    <span className="datil-label">Prioridad {s}</span>
                    <strong>{counts[s]}</strong>
                  </div>
                ))}
              </div>
              <div className="datil-lapse-bar" role="group" aria-label="Prioridad">
                {["todas", ...SEVERITIES].map((s) => (
                  <button key={s} className={s === filter ? "datil-chip active" : "datil-chip"} aria-pressed={s === filter} onClick={() => setFilter(s)}>
                    {s === "todas" ? "Todas" : `${s[0].toUpperCase()}${s.slice(1)}`}
                  </button>
                ))}
              </div>
            </section>
            <section className="datil-card">
              <h2>Quién necesita atención</h2>
              <ResponsiveContainer width="100%" height={Math.max(120, chart.length * 40)}>
                <BarChart data={chart} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="client" width={110} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  {SEVERITIES.map((s) => (
                    <Bar key={s} dataKey={s} name={s} stackId="sev" fill={COLORS[s]} maxBarSize={26} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </section>
          </div>

          <section className="datil-card">
            <h2>Sugerencias por acción</h2>
            {stocks.length === 0 && <p className="datil-period-tag">Ninguna acción tiene sugerencias con este filtro.</p>}
            {stocks.map(([symbol, items], i) => (
              <details key={symbol} open={i < 3}>
                <summary>
                  <strong>{symbol}</strong>
                  <span className="datil-period-tag">
                    {" "}
                    {new Set(items.map((s) => s.username)).size} cliente(s) · {items.length} sugerencia(s)
                  </span>
                </summary>
                <ul className="datil-suggestions">
                  {items.map((s, j) => (
                    <li key={`${s.username}-${s.id}-${j}`}>
                      <SeverityTag severity={s.severity} />{" "}
                      <button className="datil-link" onClick={() => onOpen(s.username)}>
                        {s.client}
                      </button>
                      : {s.title}
                      <span className="datil-period-tag">{s.detail}</span>
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </section>

          {general.length > 0 && (
            <section className="datil-card">
              <h2>Del portafolio completo</h2>
              <ul className="datil-suggestions">
                {general.map((s, j) => (
                  <li key={`${s.username}-${s.id}-${j}`}>
                    <SeverityTag severity={s.severity} />{" "}
                    <button className="datil-link" onClick={() => onOpen(s.username)}>
                      {s.client}
                    </button>
                    : {s.title}
                    <span className="datil-period-tag">{s.detail}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      <Ideas />
    </>
  );
}

function Ideas() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/consultant/ideas")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudieron cargar las ideas de acciones.")));
  }, []);

  return (
    <section className="datil-card">
      <h2>Ideas de acciones de riesgo bajo</h2>
      {error && <p className="datil-error">{error}</p>}
      {!error && !data && <p>Revisando acciones...</p>}
      {data && data.ideas.length === 0 && <p>Ninguna de las {data.reviewed} acciones revisadas cumple hoy.</p>}
      {data && data.ideas.length > 0 && (
        <div className="datil-table-wrap">
          <table className="datil-table">
            <thead>
              <tr>
                <th>Acción</th>
                <th>Riesgo</th>
                <th className="datil-col-num">Sobre su mínimo</th>
                <th className="datil-col-num">Bajo su máximo</th>
                <th className="datil-col-num">6 meses</th>
                <th>Por qué aparece</th>
              </tr>
            </thead>
            <tbody>
              {data.ideas.map((i) => (
                <tr key={i.symbol}>
                  <td>
                    <strong>{i.symbol}</strong>
                    <span className="datil-period-tag"> {i.name}</span>
                  </td>
                  <td>
                    <RiskBadge level={i.risk.level} score={i.risk.score} />
                  </td>
                  <td className="datil-col-num">{signed(i.facts.above_low_pct)}</td>
                  <td className="datil-col-num">{signed(i.facts.below_high_pct)}</td>
                  <td className={`datil-col-num ${i.facts.change_6m_pct >= 0 ? "datil-up" : "datil-down"}`}>{signed(i.facts.change_6m_pct)}</td>
                  <td style={{ whiteSpace: "normal" }}>{i.reasons.join(" · ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="datil-period-tag datil-section-note">
        Acciones de una lista de seguimiento con riesgo bajo (el mismo puntaje que ven los clientes) que están cerca de su mínimo de
        los últimos años o con buena tendencia. Es un filtro con datos del pasado, no una predicción: no dice que vayan a subir.
      </p>
    </section>
  );
}
