import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";

const PERIODS = [7, 30, 90];
const sign = (v) => (v >= 0 ? "var(--datil-up)" : "var(--datil-down)");
const trend = (v) => (v == null ? "" : v >= 0 ? "datil-up" : "datil-down");
const pctText = (v) => (v == null ? "N/D" : `${v > 0 ? "+" : ""}${v}%`);

// Ganancias y pérdidas (part="pnl") o activos en tendencia y movimiento de las acciones (part="market")
// de un grupo de clientes. `endpoint` decide de quién: los del consultor o todos los del admin.
export default function Insights({ endpoint, part }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    apiClient
      .get(endpoint, { params: { days } })
      .then(({ data }) => !cancelled && setData(data))
      .catch((err) => !cancelled && setError(apiError(err, "No se pudo cargar el resumen.")));
    return () => {
      cancelled = true;
    };
  }, [endpoint, days]);

  return (
    <>
      {part === "market" && (
        <div className="datil-lapse-bar" role="group" aria-label="Periodo">
          {PERIODS.map((p) => (
            <button key={p} className={p === days ? "datil-chip active" : "datil-chip"} aria-pressed={p === days} onClick={() => setDays(p)}>
              Últimos {p} días
            </button>
          ))}
        </div>
      )}
      {error && <p className="datil-error">{error}</p>}
      {!error && !data && <p>Calculando... la primera vez puede tardar unos segundos.</p>}
      {data && (part === "pnl" ? <Pnl pnl={data.pnl} /> : <Market data={data} />)}
    </>
  );
}

function Pnl({ pnl }) {
  const { totals, clients, realized_by_month: months } = pnl;
  if (clients.length === 0)
    return (
      <section className="datil-card">
        <p>Aún no hay clientes.</p>
      </section>
    );
  return (
    <section className="datil-card">
      <h2>Ganancias y pérdidas</h2>
      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Resultado total</span>
          <strong className={trend(totals.total)}>{formatCurrency(totals.total)}</strong>
        </div>
        <div>
          <span className="datil-label">En posiciones abiertas</span>
          <strong className={trend(totals.unrealized)}>{formatCurrency(totals.unrealized)}</strong>
        </div>
        <div>
          <span className="datil-label">Ya realizado (ventas)</span>
          <strong className={trend(totals.realized)}>{formatCurrency(totals.realized)}</strong>
        </div>
      </div>

      <h3 className="datil-subheading">Resultado por cliente</h3>
      <div className="datil-chart-wrapper">
        <ResponsiveContainer width="100%" height={Math.max(120, clients.length * 44)}>
          <BarChart data={clients} layout="vertical" margin={{ left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => formatCurrency(v)} />
            <YAxis type="category" dataKey="client" width={110} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => formatCurrency(v)} />
            <Bar dataKey="total" name="Resultado" maxBarSize={28}>
              {clients.map((c) => (
                <Cell key={c.username} fill={sign(c.total)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h3 className="datil-subheading">Utilidad realizada por mes</h3>
      {months.length === 0 ? (
        <p className="datil-period-tag">Aún no hay ventas con utilidad o pérdida realizada.</p>
      ) : (
        <div className="datil-chart-wrapper">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={months}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={70} tickFormatter={(v) => formatCurrency(v)} />
              <Tooltip formatter={(v) => formatCurrency(v)} />
              <Bar dataKey="realized" name="Realizado" maxBarSize={48}>
                {months.map((m) => (
                  <Cell key={m.month} fill={sign(m.realized)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

function Market({ data }) {
  const [by, setBy] = useState("month");
  const { trending, movements, days } = data;
  const { months, rows } = movements;
  // Mes a mes ordena por el último mes; año a año, por los últimos 12 meses.
  const value = (r) => (by === "month" ? r.monthly[r.monthly.length - 1] : r.year_pct);
  const ranked = rows.filter((r) => value(r) != null).sort((a, b) => value(b) - value(a));
  const extremes = ranked.length > 10 ? [...ranked.slice(0, 5), ...ranked.slice(-5)] : ranked;

  return (
    <>
      <section className="datil-card">
        <h2>En tendencia entre tus compradores</h2>
        {trending.length === 0 ? (
          <p>Sin operaciones en los últimos {days} días.</p>
        ) : (
          <div className="datil-table-wrap">
            <table className="datil-table">
              <thead>
                <tr>
                  <th>Activo</th>
                  <th className="datil-col-num">Compradores</th>
                  <th className="datil-col-num">Vendedores</th>
                  <th className="datil-col-num">Volumen</th>
                </tr>
              </thead>
              <tbody>
                {trending.map((t) => (
                  <tr key={`${t.type}-${t.symbol}`}>
                    <td>
                      <strong>{t.symbol}</strong>
                      <span className="datil-period-tag">
                        {" "}
                        {t.type === "bono" ? "Bono" : "Acción"} · {t.name}
                      </span>
                    </td>
                    <td className="datil-col-num">{t.buyers}</td>
                    <td className="datil-col-num">{t.sellers}</td>
                    <td className="datil-col-num">{formatCurrency(t.volume_mxn)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="datil-card">
        <h2>Qué acciones suben y cuáles bajan</h2>
        <p className="datil-period-tag">Las acciones que tienen o han operado los clientes.</p>
        <div className="datil-lapse-bar" role="group" aria-label="Comparar por">
          {[
            ["month", "Mes a mes"],
            ["year", "Año a año"],
          ].map(([id, label]) => (
            <button key={id} className={id === by ? "datil-chip active" : "datil-chip"} aria-pressed={id === by} onClick={() => setBy(id)}>
              {label}
            </button>
          ))}
        </div>
        {ranked.length === 0 ? (
          <p>Sin históricos de precios para comparar.</p>
        ) : (
          <>
            <div className="datil-chart-wrapper">
              <ResponsiveContainer width="100%" height={Math.max(160, extremes.length * 30)}>
                <BarChart data={extremes.map((r) => ({ symbol: r.symbol, pct: value(r) }))} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
                  <YAxis type="category" dataKey="symbol" width={70} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => `${v}%`} />
                  <Bar dataKey="pct" name={by === "month" ? "Último mes" : "Últimos 12 meses"} maxBarSize={24}>
                    {extremes.map((r) => (
                      <Cell key={r.symbol} fill={sign(value(r))} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="datil-period-tag">
              {ranked.length > 10 ? "Las 5 que más subieron y las 5 que más bajaron. " : ""}Variación del precio en su moneda.
            </p>
            <div className="datil-table-wrap">
              <table className="datil-table">
                <thead>
                  <tr>
                    <th>Acción</th>
                    <th className="datil-col-num">Clientes</th>
                    {months.map((m) => (
                      <th key={m} className="datil-col-num">
                        {m.slice(2)}
                      </th>
                    ))}
                    <th className="datil-col-num">12 meses</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((r) => (
                    <tr key={r.symbol}>
                      <td>
                        <strong>{r.symbol}</strong>
                        <span className="datil-period-tag"> {r.name}</span>
                      </td>
                      <td className="datil-col-num">{r.holders}</td>
                      {r.monthly.map((v, i) => (
                        <td key={months[i]} className={`datil-col-num ${trend(v)}`}>
                          {pctText(v)}
                        </td>
                      ))}
                      <td className={`datil-col-num ${trend(r.year_pct)}`}>{pctText(r.year_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </>
  );
}
