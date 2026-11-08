import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import ActivityFeed from "../components/ActivityFeed";
import ClientDetail from "../components/ClientDetail";
import ClientTriage, { useTriage } from "../components/ClientTriage";
import CompositionPie, { holdingEntries, slices } from "../components/CompositionPie";
import FilterBar from "../components/FilterBar";
import Insights from "../components/Insights";
import NotifyClient from "../components/NotifyClient";
import { RiskBadge } from "../components/RiskParts";
import SignalsFeed from "../components/SignalsFeed";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";

const PERIODS = [7, 30, 90];
const trend = (v) => (v >= 0 ? "datil-up" : "datil-down");

// Situaciones que el consultor quiere ver de un vistazo, y cómo ordenar su lista.
const result = (c) => c.unrealized + c.realized;
const NO_ROWS = [];
const TRIAGE = {
  tags: [
    { id: "alto", label: "Con riesgo alto", short: "con riesgo alto", attention: true, test: (c) => c.risk?.level === "alto" },
    { id: "perdiendo", label: "Perdiendo dinero", short: "perdiendo dinero", attention: true, test: (c) => result(c) < 0 },
    { id: "quietos", label: "Sin operaciones en el periodo", short: "sin operar en el periodo", test: (c) => c.buys + c.sells === 0 },
  ],
  sorts: [
    { id: "patrimonio", label: "Mayor patrimonio", cmp: (a, b) => b.total - a.total },
    { id: "mejor", label: "Mejor resultado", cmp: (a, b) => result(b) - result(a) },
    { id: "peor", label: "Peor resultado", cmp: (a, b) => result(a) - result(b) },
    { id: "nombre", label: "Nombre (A a Z)", cmp: (a, b) => a.client.localeCompare(b.client) },
  ],
  searchText: (c) => `${c.client} ${c.username}`,
};

// Panel del consultor, una sección por pestaña del menú: clientes (con sus ganancias y pérdidas), sugerencias y
// alertas en un solo lugar, tendencias y, al final, los avisos que manda. El filtro por cliente se comparte.
export default function Consultor({ section, goTo }) {
  const [selected, setSelected] = useState(null);
  const [options, setOptions] = useState([]); // todos sus clientes, para el filtro
  const [filter, setFilter] = useState({ consultant: "", client: "" });
  const [draft, setDraft] = useState(null); // aviso precargado desde una sugerencia

  useEffect(() => setSelected(null), [section?.id]);

  if (selected) return <ClientDetail username={selected} onBack={() => setSelected(null)} />;
  const id = section?.id ?? "clientes";

  return (
    <>
      {options.length > 1 && <FilterBar clients={options} value={filter} onChange={setFilter} />}
      {id === "clientes" && <ClientsView filter={filter} onOpen={setSelected} onOptions={setOptions} />}
      {id === "sugerencias" && (
        <SignalsFeed
          filter={filter}
          onOptions={setOptions}
          onOpen={setSelected}
          onNotice={(d) => {
            setDraft(d);
            goTo("avisos");
          }}
        />
      )}
      {id === "tendencias" && <Insights endpoint="/api/consultant/insights" filter={filter} />}
      {id === "avisos" && <Notices filter={filter} draft={draft} onOptions={setOptions} />}
    </>
  );
}

function ClientsView({ filter, onOpen, onOptions }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const triage = useTriage(data?.clients ?? NO_ROWS, TRIAGE);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    apiClient
      .get("/api/consultant/dashboard", { params: { days, client: filter.client || undefined } })
      .then(({ data }) => {
        if (cancelled) return;
        setData(data);
        if (!filter.client) onOptions(data.clients.map((c) => ({ username: c.username, name: c.client })));
      })
      .catch((err) => !cancelled && setError(apiError(err, "No se pudo cargar el panel.")));
    return () => {
      cancelled = true;
    };
  }, [days, filter.client]);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Calculando el riesgo de tus clientes... la primera vez puede tardar unos segundos.</p>;
  if (data.clients.length === 0)
    return (
      <section className="datil-card">
        <h2>Mis clientes</h2>
        <p>Aún no tienes clientes asignados. El administrador los asigna desde Usuarios y permisos.</p>
      </section>
    );

  const { totals } = data;
  const clients = triage.visible;
  const total = totals.unrealized + totals.realized;
  return (
    <>
      {data.clients.length > 1 && <ClientTriage triage={triage} tags={TRIAGE.tags} sorts={TRIAGE.sorts} />}
      <section className="datil-card">
        <h2>Mis clientes</h2>
        <div className="datil-lapse-bar" role="group" aria-label="Periodo">
          {PERIODS.map((p) => (
            <button key={p} className={p === days ? "datil-chip active" : "datil-chip"} aria-pressed={p === days} onClick={() => setDays(p)}>
              Últimos {p} días
            </button>
          ))}
        </div>
        <div className="datil-summary-grid">
          <div>
            <span className="datil-label">Patrimonio</span>
            <strong>{formatCurrency(totals.portfolio_total)}</strong>
          </div>
          <div>
            <span className="datil-label">Resultado total</span>
            <strong className={trend(total)}>{formatCurrency(total)}</strong>
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
            <span className="datil-label">Con riesgo alto</span>
            <strong>
              {totals.high_risk} de {totals.clients}
            </strong>
          </div>
        </div>
      </section>

      {clients.length > 0 && (
      <div className="datil-grid-2">
        <section className="datil-card">
          <h2>Ganancias y pérdidas por cliente</h2>
          <ResponsiveContainer width="100%" height={Math.max(150, clients.length * 44)}>
            <BarChart data={clients} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => formatCurrency(v)} />
              <YAxis type="category" dataKey="client" width={110} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => formatCurrency(v)} />
              <Legend />
              <Bar dataKey="unrealized" name="Sin vender" stackId="r" fill="var(--datil-accent)" maxBarSize={26} />
              <Bar dataKey="realized" name="Realizado" stackId="r" fill="var(--datil-text-muted)" maxBarSize={26} />
            </BarChart>
          </ResponsiveContainer>
        </section>
        <section className="datil-card">
          <h2>Operaciones por día</h2>
          <ResponsiveContainer width="100%" height={Math.max(150, clients.length * 44)}>
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
        </section>
      </div>
      )}

      {clients.length > 0 && (
      <div className="datil-grid-2">
        {clients.length > 1 && <CompositionPie title="Patrimonio por cliente" data={slices(clients.map((c) => ({ name: c.client, value: c.portfolio })))} />}
        <CompositionPie title="Qué hay en las carteras" data={slices(holdingEntries(clients))} />
      </div>
      )}

      <section className="datil-card">
        <h2>Clientes</h2>
        <div className="datil-table-wrap">
          <table className="datil-table">
            <thead>
              <tr>
                <th>Cliente</th>
                <th className="datil-col-num">Portafolio</th>
                <th className="datil-col-num">Resultado</th>
                <th>Riesgo de sus acciones</th>
                <th className="datil-col-num">Compras / ventas</th>
                <th className="datil-col-num">Volumen</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {clients.length === 0 && (
                <tr>
                  <td colSpan={7} className="datil-empty-row">
                    Ningún cliente coincide con el filtro.{" "}
                    <button type="button" className="datil-link" onClick={triage.clear}>
                      Quitar filtros
                    </button>
                  </td>
                </tr>
              )}
              {clients.map((c) => (
                <tr key={c.username}>
                  <td>
                    <strong>{c.client}</strong>
                    <span className="datil-period-tag"> {c.username}</span>
                  </td>
                  <td className="datil-col-num">{formatCurrency(c.total)}</td>
                  <td className={`datil-col-num ${trend(result(c))}`}>{formatCurrency(result(c))}</td>
                  <td>{c.risk && c.risk.level ? <RiskBadge level={c.risk.level} score={c.risk.score} /> : <span className="datil-period-tag">N/D</span>}</td>
                  <td className="datil-col-num">
                    {c.buys} / {c.sells}
                  </td>
                  <td className="datil-col-num">{formatCurrency(c.volume_mxn)}</td>
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
      </section>

      <div className="datil-grid-2">
        <section className="datil-card">
          <h2>Mejores compras</h2>
          <TopTable
            rows={data.top_positions}
            empty="Sin posiciones con rendimiento calculado."
            columns={[
              ["Posición", (r) => `${r.symbol} · ${r.name}`],
              ["Rendimiento", (r) => `${formatCurrency(r.gain_mxn)} (${r.gain_percent}%)`, true],
            ]}
          />
        </section>
        <section className="datil-card">
          <h2>Mejores ventas de los últimos {data.days} días</h2>
          <TopTable
            rows={data.top_sales}
            empty="Sin ventas con utilidad realizada en el periodo."
            columns={[
              ["Venta", (r) => `${r.symbol} · ${r.name}`],
              ["Fecha", (r) => r.date],
              ["Utilidad", (r) => formatCurrency(r.realized_pnl_mxn), true],
            ]}
          />
        </section>
      </div>
      <p className="datil-period-tag">Son resultados ya ocurridos, para conocer a los clientes; no indican que vayan a repetirse.</p>

      <ActivityFeed filter={filter} />
    </>
  );
}

// Avisos, al final del menú: se mandan a un cliente (a veces desde una sugerencia) y aquí queda el registro con fecha y hora.
function Notices({ filter, draft, onOptions }) {
  const [options, setOptions] = useState([]);
  const [client, setClient] = useState(draft?.username ?? filter.client ?? "");
  const [version, setVersion] = useState(0); // al enviar, se vuelve a pedir el registro

  useEffect(() => {
    apiClient.get("/api/consultant/dashboard").then(({ data }) => {
      const list = data.clients.map((c) => ({ username: c.username, name: c.client }));
      setOptions(list);
      onOptions(list);
    });
  }, []);

  return (
    <>
      <section className="datil-card">
        <h2>Nuevo aviso</h2>
        <label>
          Para qué cliente
          <select value={client} onChange={(e) => setClient(e.target.value)}>
            <option value="">Elige un cliente</option>
            {options.map((c) => (
              <option key={c.username} value={c.username}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        {client && <NotifyClient username={client} draft={draft && draft.username === client ? draft : null} hideSent embedded onSent={() => setVersion((v) => v + 1)} />}
      </section>
      <ActivityFeed key={version} kind="avisos" filter={filter} />
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
