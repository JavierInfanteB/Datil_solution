import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import ClientDetail from "../components/ClientDetail";
import { RiskBadge, SeverityTag } from "../components/RiskParts";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";

const PERIODS = [7, 30, 90];

// Panel del consultor: sus clientes asignados, qué hicieron los últimos días, cómo están de riesgo y
// qué decisiones conviene tomar. Al abrir un cliente se ve su detalle.
export default function Consultor() {
  const [selected, setSelected] = useState(null);
  return selected ? (
    <ClientDetail username={selected} onBack={() => setSelected(null)} />
  ) : (
    <Dashboard onOpen={setSelected} />
  );
}

function Dashboard({ onOpen }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    apiClient
      .get("/api/consultant/dashboard", { params: { days } })
      .then(({ data }) => !cancelled && setData(data))
      .catch((err) => !cancelled && setError(apiError(err, "No se pudo cargar el panel.")));
    return () => {
      cancelled = true;
    };
  }, [days]);

  return (
    <>
      <section className="datil-card">
        <h2>Mis clientes</h2>
        <div className="datil-lapse-bar" role="group" aria-label="Periodo">
          {PERIODS.map((p) => (
            <button
              key={p}
              className={p === days ? "datil-chip active" : "datil-chip"}
              aria-pressed={p === days}
              onClick={() => setDays(p)}
            >
              Últimos {p} días
            </button>
          ))}
        </div>
        {error && <p className="datil-error">{error}</p>}
        {!error && !data && <p>Calculando el riesgo de tus clientes... la primera vez puede tardar unos segundos.</p>}
        {data && data.clients.length === 0 && (
          <p>Aún no tienes clientes asignados. El administrador los asigna desde Usuarios y permisos.</p>
        )}
        {data && data.clients.length > 0 && <Summary data={data} onOpen={onOpen} />}
      </section>

      {data && data.clients.length > 0 && (
        <>
          <section className="datil-card">
            <h2>Sugerencias para reducir riesgo</h2>
            {data.suggestions.length === 0 ? (
              <p>Ningún cliente tiene alertas por ahora.</p>
            ) : (
              <ul className="datil-suggestions">
                {data.suggestions.map((s, i) => (
                  <li key={`${s.username}-${s.id}-${i}`}>
                    <SeverityTag severity={s.severity} />{" "}
                    <button className="datil-link" onClick={() => onOpen(s.username)}>
                      {s.client}
                    </button>
                    : <strong>{s.title}</strong>
                    <span className="datil-period-tag"> {s.detail}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="datil-card">
            <h2>Lo mejor del periodo</h2>
            <h3 className="datil-subheading">Mejores compras (rendimiento actual de la posición)</h3>
            <TopTable
              rows={data.top_positions}
              empty="Sin posiciones con rendimiento calculado."
              columns={[
                ["Posición", (r) => `${r.symbol} · ${r.name}`],
                ["Rendimiento", (r) => `${formatCurrency(r.gain_mxn)} (${r.gain_percent}%)`, true],
              ]}
            />
            <h3 className="datil-subheading">Mejores ventas (utilidad realizada en los últimos {data.days} días)</h3>
            <TopTable
              rows={data.top_sales}
              empty="Sin ventas con utilidad realizada en el periodo."
              columns={[
                ["Venta", (r) => `${r.symbol} · ${r.name}`],
                ["Fecha", (r) => r.date],
                ["Utilidad", (r) => formatCurrency(r.realized_pnl_mxn), true],
              ]}
            />
            <p className="datil-period-tag">
              Son resultados ya ocurridos, para conocer a los clientes; no indican que vayan a repetirse.
            </p>
          </section>
        </>
      )}
    </>
  );
}

function Summary({ data, onOpen }) {
  const { totals } = data;
  return (
    <>
      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Clientes</span>
          <strong>{totals.clients}</strong>
        </div>
        <div>
          <span className="datil-label">Patrimonio de tus clientes</span>
          <strong>{formatCurrency(totals.portfolio_total)}</strong>
        </div>
        <div>
          <span className="datil-label">Compras / ventas</span>
          <strong>
            {totals.buys} / {totals.sells}
          </strong>
        </div>
        <div>
          <span className="datil-label">Volumen operado</span>
          <strong>{formatCurrency(totals.volume_mxn)}</strong>
        </div>
        <div>
          <span className="datil-label">Clientes con riesgo alto</span>
          <strong>{totals.high_risk}</strong>
        </div>
        <div>
          <span className="datil-label">Alertas de prioridad alta</span>
          <strong>{totals.alerts}</strong>
        </div>
      </div>

      <h3 className="datil-subheading">Operaciones por día</h3>
      <div className="datil-chart-wrapper">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data.activity}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} tickFormatter={(d) => d.slice(5)} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={30} />
            <Tooltip />
            <Legend />
            <Bar dataKey="buys" name="Compras" stackId="ops" fill="var(--datil-accent)" />
            <Bar dataKey="sells" name="Ventas" stackId="ops" fill="var(--datil-text-muted)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h3 className="datil-subheading">Clientes</h3>
      <div className="datil-table-wrap">
        <table className="datil-table">
          <thead>
            <tr>
              <th>Cliente</th>
              <th className="datil-col-num">Portafolio</th>
              <th>Riesgo de sus acciones</th>
              <th className="datil-col-num">Compras / ventas</th>
              <th className="datil-col-num">Volumen</th>
              <th className="datil-col-num">Alertas altas</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.clients.map((c) => (
              <tr key={c.username}>
                <td>
                  <strong>{c.client}</strong>
                  <span className="datil-period-tag"> {c.username}</span>
                </td>
                <td className="datil-col-num">{formatCurrency(c.total)}</td>
                <td>{c.risk && c.risk.level ? <RiskBadge level={c.risk.level} score={c.risk.score} /> : <span className="datil-period-tag">N/D</span>}</td>
                <td className="datil-col-num">
                  {c.buys} / {c.sells}
                </td>
                <td className="datil-col-num">{formatCurrency(c.volume_mxn)}</td>
                <td className="datil-col-num">{c.alerts}</td>
                <td>
                  <button className="datil-btn datil-btn-secondary" onClick={() => onOpen(c.username)}>
                    Ver detalle
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// Monto de una fila de "lo mejor": ganancia de la posición o utilidad de la venta.
const amountOf = (row) => row.gain_mxn ?? row.realized_pnl_mxn;

// columns: [encabezado, función(fila) -> texto, esNumerica?]
function TopTable({ rows, columns, empty }) {
  if (rows.length === 0) return <p className="datil-period-tag">{empty}</p>;
  return (
    <div className="datil-table-wrap">
      <table className="datil-table">
        <thead>
          <tr>
            <th>Cliente</th>
            {columns.map(([title, , numeric]) => (
              <th key={title} className={numeric ? "datil-col-num" : undefined}>
                {title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.username}-${r.symbol}-${i}`}>
              <td>{r.client}</td>
              {columns.map(([title, cell, numeric]) => (
                <td key={title} className={numeric ? `datil-col-num ${amountOf(r) >= 0 ? "datil-up" : "datil-down"}` : undefined}>
                  {cell(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
