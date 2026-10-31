import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";

const sign = (v) => (v >= 0 ? "var(--datil-up)" : "var(--datil-down)");
const trend = (v) => (v == null ? "" : v >= 0 ? "datil-up" : "datil-down");

// Ganancias y pérdidas del admin, vistas por consultor: quién rinde y quién es constante. Al elegir un consultor
// se ve el resultado de cada uno de sus clientes.
export default function ConsultantsOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [picked, setPicked] = useState(null); // usuario del consultor elegido; null = todos

  useEffect(() => {
    apiClient
      .get("/api/admin/consultants")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudo cargar el resumen de consultores.")));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Calculando el resultado de cada consultor...</p>;

  const { consultants, totals } = data;
  const one = consultants.find((c) => c.username === picked);
  const chart = one ? one.clients_detail.map((c) => ({ label: c.client, total: c.total })) : consultants.map((c) => ({ label: c.name, total: c.total }));
  const head = one ?? { ...totals, clients: consultants.reduce((n, c) => n + c.clients, 0) };

  return (
    <>
      <section className="datil-card">
        <h2>Ganancias y pérdidas por consultor</h2>
        <div className="datil-lapse-bar" role="group" aria-label="Consultor">
          <button className={picked === null ? "datil-chip active" : "datil-chip"} aria-pressed={picked === null} onClick={() => setPicked(null)}>
            Todos
          </button>
          {consultants.map((c) => (
            <button key={c.username} className={picked === c.username ? "datil-chip active" : "datil-chip"} aria-pressed={picked === c.username} onClick={() => setPicked(c.username)}>
              {c.name}
            </button>
          ))}
        </div>
        <div className="datil-summary-grid">
          <div>
            <span className="datil-label">Resultado total</span>
            <strong className={trend(head.total)}>{formatCurrency(head.total)}</strong>
          </div>
          <div>
            <span className="datil-label">Sin vender</span>
            <strong className={trend(head.unrealized)}>{formatCurrency(head.unrealized)}</strong>
          </div>
          <div>
            <span className="datil-label">Ya realizado</span>
            <strong className={trend(head.realized)}>{formatCurrency(head.realized)}</strong>
          </div>
          <div>
            <span className="datil-label">Patrimonio de clientes</span>
            <strong>{formatCurrency(head.portfolio)}</strong>
          </div>
        </div>

        <h3 className="datil-subheading">{one ? `Resultado de los clientes de ${one.name}` : "Resultado por consultor"}</h3>
        <div className="datil-chart-wrapper">
          <ResponsiveContainer width="100%" height={Math.max(130, chart.length * 44)}>
            <BarChart data={chart} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => formatCurrency(v)} />
              <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => formatCurrency(v)} />
              <Bar dataKey="total" name="Resultado" maxBarSize={28}>
                {chart.map((c) => (
                  <Cell key={c.label} fill={sign(c.total)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="datil-card">
        <h2>{one ? `Clientes de ${one.name}` : "Qué consultores funcionan"}</h2>
        <div className="datil-table-wrap">
          {one ? <ClientsTable rows={one.clients_detail} /> : <KpiTable rows={consultants} onPick={setPicked} />}
        </div>
        {!one && (
          <p className="datil-period-tag datil-section-note">
            Constancia: de las últimas 12 semanas, en cuántas el consultor hizo algo por sus clientes (avisos, alertas o notas).
            Rendimiento: ganancia sin vender sobre lo que cuestan las posiciones abiertas.
          </p>
        )}
      </section>
    </>
  );
}

function KpiTable({ rows, onPick }) {
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
            <td>
              {c.username ? (
                <button className="datil-link" onClick={() => onPick(c.username)}>
                  {c.name}
                </button>
              ) : (
                <span className="datil-period-tag">{c.name}</span>
              )}
            </td>
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

function ClientsTable({ rows }) {
  if (rows.length === 0) return <p className="datil-period-tag">Este consultor aún no tiene clientes.</p>;
  return (
    <table className="datil-table">
      <thead>
        <tr>
          <th>Cliente</th>
          <th className="datil-col-num">Patrimonio</th>
          <th className="datil-col-num">Sin vender</th>
          <th className="datil-col-num">Realizado</th>
          <th className="datil-col-num">Resultado</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => (
          <tr key={c.username}>
            <td>{c.client}</td>
            <td className="datil-col-num">{formatCurrency(c.portfolio)}</td>
            <td className={`datil-col-num ${trend(c.unrealized)}`}>{formatCurrency(c.unrealized)}</td>
            <td className={`datil-col-num ${trend(c.realized)}`}>{formatCurrency(c.realized)}</td>
            <td className={`datil-col-num ${trend(c.total)}`}>{formatCurrency(c.total)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
