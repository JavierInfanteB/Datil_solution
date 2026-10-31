import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import ClientDetail from "../components/ClientDetail";
import { LEVEL, ruleText } from "../components/AlertsPanel";
import Insights from "../components/Insights";
import { RiskBadge } from "../components/RiskParts";
import Suggestions from "../components/Suggestions";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";

const PERIODS = [7, 30, 90];

// Panel del consultor, una sección por pestaña del menú lateral: resumen de ganancias y pérdidas, clientes,
// sugerencias y tendencias. Al abrir un cliente se ve su detalle.
export default function Consultor({ section }) {
  const [selected, setSelected] = useState(null);
  if (selected) return <ClientDetail username={selected} onBack={() => setSelected(null)} />;
  switch (section?.id) {
    case "resumen":
      return <Insights endpoint="/api/consultant/insights" part="pnl" />;
    case "tendencias":
      return <Insights endpoint="/api/consultant/insights" part="market" />;
    case "alertas":
      return <AlertsDashboard onOpen={setSelected} />;
    default:
      return <Dashboard onOpen={setSelected} view={section?.id === "sugerencias" ? "sugerencias" : "clientes"} />;
  }
}

function Dashboard({ onOpen, view }) {
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
        <h2>{view === "sugerencias" ? "Sugerencias" : "Mis clientes"}</h2>
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
        {data && data.clients.length > 0 && view === "clientes" && <Summary data={data} onOpen={onOpen} />}
        {data && data.clients.length > 0 && view === "sugerencias" && <Suggestions data={data} onOpen={onOpen} />}
      </section>

      {data && data.clients.length > 0 && view === "clientes" && (
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

// Alertas de todos sus clientes de un vistazo: las cumplidas primero, luego las que van al 80% y al 60% del umbral,
// para que el consultor se adelante a lo que puede pasar.
function AlertsDashboard({ onOpen }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/consultant/alerts")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudieron cargar las alertas.")));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Revisando las alertas de tus clientes...</p>;

  const watched = data.alerts.filter((a) => a.level > 0);
  return (
    <section className="datil-card">
      <h2>Alertas de mis clientes</h2>
      <div className="datil-summary-grid">
        {[3, 2, 1].map((level) => (
          <div key={level}>
            <span className="datil-label">{LEVEL[level].label}</span>
            <strong>{data.counts[level]}</strong>
          </div>
        ))}
        <div>
          <span className="datil-label">Lejos de cumplirse</span>
          <strong>{data.counts[0]}</strong>
        </div>
      </div>
      {watched.length === 0 ? (
        <p>Ninguna alerta está cerca de cumplirse. Los clientes pueden ponerlas en Mi plan, y tú desde el detalle de cada uno.</p>
      ) : (
        <div className="datil-table-wrap">
          <table className="datil-table">
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Activo</th>
                <th>Regla</th>
                <th className="datil-col-num">Hoy</th>
                <th>Estado</th>
                <th>Indicación</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {watched.map((a) => (
                <tr key={a.id}>
                  <td>{a.client}</td>
                  <td>
                    <strong>{a.symbol === "*" ? "Portafolio" : a.symbol}</strong>
                  </td>
                  <td>{ruleText(a)}</td>
                  <td className={`datil-col-num ${a.move >= 0 ? "datil-up" : "datil-down"}`}>{a.move}%</td>
                  <td>
                    <span className={`datil-risk ${LEVEL[a.level].cls}`}>{LEVEL[a.level].label}</span>
                  </td>
                  <td>{a.indication === "aviso" ? "Solo avisar" : a.indication === "vender" ? "Considerar vender" : "Considerar comprar más"}</td>
                  <td>
                    <button className="datil-btn datil-btn-secondary" onClick={() => onOpen(a.username)}>
                      Ver cliente
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="datil-period-tag">
        Con una alerta de 10% de pérdida, ves el aviso desde el 6% (atención) y el 8% (cerca); al llegar al 10% también se le avisa al
        cliente. Se revisan cuando abres esta pantalla.
      </p>
    </section>
  );
}
