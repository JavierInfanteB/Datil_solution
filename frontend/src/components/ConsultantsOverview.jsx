import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";
import CompositionPie, { holdingEntries, slices } from "./CompositionPie";

const sign = (v) => (v >= 0 ? "var(--datil-up)" : "var(--datil-down)");
const trend = (v) => (v == null ? "" : v >= 0 ? "datil-up" : "datil-down");
const sum = (rows, key) => rows.reduce((n, r) => n + r[key], 0);

// Ganancias y pérdidas del admin: por defecto de todos los consultores; con el filtro, de un consultor o de un cliente.
// Dos pasteles muestran cómo se reparte el patrimonio y qué hay en las carteras.
export default function ConsultantsOverview({ filter, onOpenClients }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/admin/consultants")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudo cargar el resumen de consultores.")));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Calculando el resultado de cada consultor...</p>;

  const { consultants } = data;
  const everyone = consultants.flatMap((c) => c.clients_detail.map((cl) => ({ ...cl, consultant: c.username })));
  const scope = everyone.filter((c) => (!filter.consultant || c.consultant === filter.consultant) && (!filter.client || c.username === filter.client));
  const grouped = !filter.consultant && !filter.client; // sin filtro se compara entre consultores
  const owner = filter.client ? everyone.find((c) => c.username === filter.client)?.consultant : filter.consultant;
  const kpis = consultants.filter((c) => !owner || c.username === owner);

  const bars = grouped
    ? consultants.map((c) => ({ label: c.name, total: c.total }))
    : scope.map((c) => ({ label: c.client, total: c.total }));
  const split = grouped
    ? consultants.map((c) => ({ name: c.name, value: c.portfolio }))
    : scope.map((c) => ({ name: c.client, value: c.portfolio }));

  return (
    <>
      <section className="datil-card">
        <h2>Ganancias y pérdidas</h2>
        <div className="datil-summary-grid">
          <div>
            <span className="datil-label">Resultado total</span>
            <strong className={trend(sum(scope, "total"))}>{formatCurrency(sum(scope, "total"))}</strong>
          </div>
          <div>
            <span className="datil-label">Sin vender</span>
            <strong className={trend(sum(scope, "unrealized"))}>{formatCurrency(sum(scope, "unrealized"))}</strong>
          </div>
          <div>
            <span className="datil-label">Ya realizado</span>
            <strong className={trend(sum(scope, "realized"))}>{formatCurrency(sum(scope, "realized"))}</strong>
          </div>
          <div>
            <span className="datil-label">Patrimonio</span>
            <strong>{formatCurrency(sum(scope, "portfolio"))}</strong>
          </div>
        </div>

        <h3 className="datil-subheading">{grouped ? "Resultado por consultor" : "Resultado por cliente"}</h3>
        {bars.length === 0 ? (
          <p className="datil-period-tag">Sin datos con estos filtros.</p>
        ) : (
          <div className="datil-chart-wrapper">
            <ResponsiveContainer width="100%" height={Math.max(130, bars.length * 44)}>
              <BarChart data={bars} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => formatCurrency(v)} />
                <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => formatCurrency(v)} />
                <Bar dataKey="total" name="Resultado" maxBarSize={28}>
                  {bars.map((c) => (
                    <Cell key={c.label} fill={sign(c.total)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <div className="datil-grid-2">
        <CompositionPie title={grouped ? "Patrimonio por consultor" : "Patrimonio por cliente"} data={slices(split)} />
        <CompositionPie title="Qué hay en las carteras" data={slices(holdingEntries(scope))} />
      </div>

      <LoadCards all={consultants} rows={kpis} onOpen={onOpenClients} />

      <section className="datil-card">
        <h2>Todas las cifras por consultor</h2>
        <details>
          <summary>Ver la tabla completa</summary>
          <div className="datil-table-wrap">
            <KpiTable rows={kpis} />
          </div>
          <p className="datil-period-tag datil-section-note">
            Constancia: de las últimas 12 semanas, en cuántas el consultor hizo algo por sus clientes (avisos, alertas o notas).
            Rendimiento: ganancia sin vender sobre lo que cuestan las posiciones abiertas.
          </p>
        </details>
      </section>
    </>
  );
}

// Estado de un consultor en una frase corta: qué tanto trabajo lleva y si necesita seguimiento.
function loadStatus(c) {
  if (c.clients > 0 && c.actions_30d === 0) return { tone: "warn", text: "Sin acciones en 30 días" };
  if (c.alerts_open > 0) return { tone: "warn", text: `${c.alerts_open} ${c.alerts_open === 1 ? "alerta abierta" : "alertas abiertas"}` };
  return { tone: "ok", text: "Al día" };
}

// Una tarjeta por consultor (carga de clientes, patrimonio, constancia) para ver de un vistazo quién necesita seguimiento.
function LoadCards({ all, rows, onOpen }) {
  const people = rows.filter((c) => c.username);
  if (people.length === 0) return null;
  const pending = all.filter((c) => c.username && loadStatus(c).tone === "warn").length;
  const orphans = all.find((c) => !c.username)?.clients ?? 0;
  return (
    <section className="datil-card">
      <h2>Carga y atención por consultor</h2>
      <p className="datil-triage-headline">
        {pending === 0 ? "Todos los consultores están al día." : <><strong>{pending}</strong> {pending === 1 ? "consultor necesita" : "consultores necesitan"} seguimiento.</>}
        {orphans > 0 && <> Hay <strong>{orphans}</strong> {orphans === 1 ? "cliente" : "clientes"} sin consultor.</>}
      </p>
      <div className="datil-load-grid">
        {people.map((c) => {
          const st = loadStatus(c);
          return (
            <article key={c.username} className="datil-load-card">
              <header>
                <strong>{c.name}</strong>
                <span className={`datil-load-tag ${st.tone}`}>{st.text}</span>
              </header>
              <dl>
                <div>
                  <dt>Clientes</dt>
                  <dd>{c.clients}</dd>
                </div>
                <div>
                  <dt>Patrimonio</dt>
                  <dd>{formatCurrency(c.portfolio)}</dd>
                </div>
                <div>
                  <dt>Resultado</dt>
                  <dd className={trend(c.total)}>{formatCurrency(c.total)}</dd>
                </div>
              </dl>
              <div className="datil-progress" role="img" aria-label={`Constancia ${c.consistency}%`}>
                <div style={{ width: `${c.consistency}%` }} />
              </div>
              <span className="datil-period-tag">
                Constancia {c.consistency}% · última acción: {c.last_action ?? "nunca"}
              </span>
              {onOpen && (
                <button type="button" className="datil-btn datil-btn-secondary" onClick={() => onOpen(c.username)}>
                  Ver sus clientes
                </button>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function KpiTable({ rows }) {
  return (
    <table className="datil-table">
      <thead>
        <tr>
          <th>Consultor</th>
          <th className="datil-col-num">Clientes</th>
          <th className="datil-col-num">Patrimonio</th>
          <th className="datil-col-num">Resultado</th>
          <th className="datil-col-num">Rendimiento</th>
          <th className="datil-col-num">En ganancia</th>
          <th>Constancia</th>
          <th className="datil-col-num">Acciones 30 d</th>
          <th className="datil-col-num">Alertas</th>
          <th>Última acción</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => (
          <tr key={c.username || c.name}>
            <td>{c.username ? <strong>{c.name}</strong> : <span className="datil-period-tag">{c.name}</span>}</td>
            <td className="datil-col-num">{c.clients}</td>
            <td className="datil-col-num">{formatCurrency(c.portfolio)}</td>
            <td className={`datil-col-num ${trend(c.total)}`}>{formatCurrency(c.total)}</td>
            <td className={`datil-col-num ${trend(c.return_pct)}`}>{c.return_pct == null ? "N/D" : `${c.return_pct}%`}</td>
            <td className="datil-col-num">
              {c.in_profit} de {c.clients}
            </td>
            <td style={{ minWidth: 110 }}>
              {c.username ? (
                <>
                  <div className="datil-progress" role="img" aria-label={`Constancia ${c.consistency}%`}>
                    <div style={{ width: `${c.consistency}%` }} />
                  </div>
                  <span className="datil-period-tag">{c.consistency}%</span>
                </>
              ) : (
                <span className="datil-period-tag">N/A</span>
              )}
            </td>
            <td className="datil-col-num">{c.actions_30d}</td>
            <td className="datil-col-num">{c.alerts_open}</td>
            <td>{c.last_action ?? <span className="datil-period-tag">Nunca</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
