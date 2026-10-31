import { useEffect, useState } from "react";
import apiClient from "../api/client";
import ActivityFeed from "../components/ActivityFeed";
import ConsultantsOverview from "../components/ConsultantsOverview";
import Insights from "../components/Insights";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";
import Portfolio from "./Portfolio";
import Trading from "./Trading";

const TABS = [
  { id: "cartera", name: "Cartera" },
  { id: "accion", name: "Comprar / vender acciones" },
  { id: "bono", name: "Comprar / vender bonos y CETES" },
];

// Módulo del admin sobre los clientes de Datil: todos sus clientes, resultados y tendencias. El admin no tiene
// cartera propia: compra y vende solo en nombre de un cliente, y cada operación queda en la bitácora.
export default function AdminClients({ section }) {
  const [selected, setSelected] = useState(null);
  if (section?.id === "resumen") return <ConsultantsOverview />;
  if (section?.id === "tendencias") return <Insights endpoint="/api/admin/insights" part="market" />;
  return selected ? <ClientOperate client={selected} onBack={() => setSelected(null)} /> : <ClientList onOpen={setSelected} />;
}

function ClientList({ onOpen }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/admin/clients")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudieron cargar los clientes.")));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Cargando clientes...</p>;

  const rows = data.clients.filter((c) => `${c.name} ${c.username}`.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <>
      <section className="datil-card">
        <h2>Clientes de Datil Solution</h2>
        <label>
          Buscar
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nombre o usuario" />
        </label>
        <div className="datil-table-wrap">
          <table className="datil-table">
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Consultor</th>
                <th className="datil-col-num">Patrimonio</th>
                <th className="datil-col-num">Ganancia o pérdida</th>
                <th className="datil-col-num">Posiciones</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.username}>
                  <td>
                    <strong>{c.name}</strong>
                    <span className="datil-period-tag"> {c.username}{c.disabled ? " · suspendido" : ""}</span>
                  </td>
                  <td>{c.consultant ?? <span className="datil-period-tag">Sin consultor</span>}</td>
                  <td className="datil-col-num">{formatCurrency(c.total)}</td>
                  <td className={`datil-col-num ${c.gain_mxn >= 0 ? "datil-up" : "datil-down"}`}>{formatCurrency(c.gain_mxn)}</td>
                  <td className="datil-col-num">{c.holdings_count}</td>
                  <td>
                    <button className="datil-btn datil-btn-secondary" disabled={c.disabled} onClick={() => onOpen(c)}>
                      Ver y operar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="datil-period-tag">Cambiar contraseñas, suspender cuentas o asignar consultor se hace en Usuarios y permisos.</p>
      </section>

      <ActivityFeed />
    </>
  );
}

function ClientOperate({ client, onBack }) {
  const [tab, setTab] = useState("cartera");
  const section = TABS.find((t) => t.id === tab);
  return (
    <>
      <div className="datil-actions">
        <button className="datil-btn datil-btn-secondary" onClick={onBack}>
          Volver a los clientes
        </button>
      </div>
      <section className="datil-card">
        <h2>Operando en nombre de {client.name}</h2>
        <p className="datil-period-tag">Todo lo que compres o vendas aquí es de este cliente y queda en la bitácora.</p>
        <div className="datil-lapse-bar" role="group" aria-label="Sección">
          {TABS.map((t) => (
            <button key={t.id} className={t.id === tab ? "datil-chip active" : "datil-chip"} aria-pressed={t.id === tab} onClick={() => setTab(t.id)}>
              {t.name}
            </button>
          ))}
        </div>
      </section>
      {tab === "cartera" ? <Portfolio client={client.username} /> : <Trading key={tab} section={section} client={client.username} />}
    </>
  );
}
