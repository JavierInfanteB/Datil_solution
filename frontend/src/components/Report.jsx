import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";

const PERIODS = [
  ["month", "Este mes"],
  ["quarter", "Este trimestre"],
  ["year", "Este año"],
];
const trend = (v) => (v >= 0 ? "datil-up" : "datil-down");

// Reporte de un cliente por mes, trimestre o año: qué logró, ingresos, qué puede mejorar y gráficas.
// `endpoint` es el del propio cliente (/api/plan/report) o el que lee su consultor.
export default function Report({ endpoint }) {
  const [period, setPeriod] = useState("month");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    apiClient
      .get(endpoint, { params: { period } })
      .then(({ data }) => !cancelled && setData(data))
      .catch((err) => !cancelled && setError(apiError(err, "No se pudo armar el reporte.")));
    return () => {
      cancelled = true;
    };
  }, [endpoint, period]);

  return (
    <>
      <div className="datil-lapse-bar" role="group" aria-label="Periodo del reporte">
        {PERIODS.map(([id, label]) => (
          <button key={id} className={id === period ? "datil-chip active" : "datil-chip"} aria-pressed={id === period} onClick={() => setPeriod(id)}>
            {label}
          </button>
        ))}
      </div>
      {error && <p className="datil-error">{error}</p>}
      {!error && !data && <p>Armando el reporte...</p>}
      {data && <Body r={data} />}
    </>
  );
}

function Body({ r }) {
  return (
    <>
      <p className="datil-period-tag">
        Del {r.start} al {r.end}.
      </p>
      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Utilidad realizada</span>
          <strong className={trend(r.realized)}>{formatCurrency(r.realized)}</strong>
        </div>
        <div>
          <span className="datil-label">Ingresos por cupones</span>
          <strong>{formatCurrency(r.income)}</strong>
        </div>
        <div>
          <span className="datil-label">Ganancia sin vender hoy</span>
          <strong className={trend(r.unrealized)}>{formatCurrency(r.unrealized)}</strong>
        </div>
        <div>
          <span className="datil-label">Patrimonio</span>
          <strong>{formatCurrency(r.portfolio_total)}</strong>
        </div>
        <div>
          <span className="datil-label">Operaciones</span>
          <strong>
            {r.trades.count} · {formatCurrency(r.trades.volume_mxn)}
          </strong>
        </div>
      </div>

      <h3 className="datil-subheading">Resultado del periodo</h3>
      <div className="datil-chart-wrapper">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={r.series}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={70} tickFormatter={(v) => formatCurrency(v)} />
            <Tooltip formatter={(v) => formatCurrency(v)} />
            <Legend />
            <Bar dataKey="realized" name="Utilidad realizada">
              {r.series.map((s) => (
                <Cell key={s.label} fill={s.realized >= 0 ? "var(--datil-up)" : "var(--datil-down)"} />
              ))}
            </Bar>
            <Bar dataKey="income" name="Cupones" fill="var(--datil-accent)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {(r.best_sale || r.worst_sale) && (
        <p className="datil-period-tag">
          {r.best_sale && `Mejor venta: ${r.best_sale.symbol} (${formatCurrency(r.best_sale.realized_pnl_mxn)}). `}
          {r.worst_sale && r.worst_sale.realized_pnl_mxn < 0 && `Peor venta: ${r.worst_sale.symbol} (${formatCurrency(r.worst_sale.realized_pnl_mxn)}).`}
        </p>
      )}

      <h3 className="datil-subheading">Lo que se logró</h3>
      <ul className="datil-suggestions">
        {r.achievements.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
      <h3 className="datil-subheading">Qué se puede mejorar</h3>
      {r.improvements.length === 0 ? (
        <p className="datil-period-tag">Sin pendientes.</p>
      ) : (
        <ul className="datil-suggestions">
          {r.improvements.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      )}

      {r.goals.length > 0 && (
        <>
          <h3 className="datil-subheading">Avance de metas</h3>
          <Goals goals={r.goals} />
        </>
      )}
    </>
  );
}

// Agrega a cada meta el avance (%) del patrimonio de hoy contra su monto.
export const withProgress = (goals, total) => goals.map((g) => ({ ...g, progress_pct: Math.round((total / g.target_mxn) * 1000) / 10 }));

// Metas con su avance: patrimonio actual contra el monto que se quiere alcanzar.
export function Goals({ goals }) {
  return (
    <ul className="datil-suggestions">
      {goals.map((g) => (
        <li key={g.id}>
          <strong>{g.title}</strong>: {formatCurrency(g.target_mxn)}
          {g.target_date && <span className="datil-period-tag"> para {g.target_date}</span>}
          <div className="datil-meter" role="img" aria-label={`Avance ${g.progress_pct}%`}>
            <div style={{ width: `${Math.min(g.progress_pct, 100)}%`, height: "100%", background: "var(--datil-accent)" }} />
          </div>
          <span className="datil-period-tag">{g.progress_pct}% con el patrimonio de hoy</span>
        </li>
      ))}
    </ul>
  );
}
