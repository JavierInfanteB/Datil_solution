import { useEffect, useState } from "react";
import apiClient from "../api/client";
import ActivityFeed from "../components/ActivityFeed";
import ConsultantsOverview from "../components/ConsultantsOverview";
import FilterBar from "../components/FilterBar";
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

// Módulo del admin sobre los clientes de Datil. El filtro por consultor y por cliente se comparte entre sus pestañas; sin
// filtro se ve todo. El admin no tiene cartera propia: compra y vende solo en nombre de un cliente y queda registrado.
export default function AdminClients({ section }) {
  const [selected, setSelected] = useState(null);
  const [people, setPeople] = useState(null);
  const [filter, setFilter] = useState({ consultant: "", client: "" });

  useEffect(() => {
    apiClient.get("/api/users").then(({ data }) => setPeople(data.users));
  }, []);
  useEffect(() => setSelected(null), [section?.id]);

  if (selected) return <ClientOperate client={selected} onBack={() => setSelected(null)} />;
  const id = section?.id ?? "lista";
  return (
    <>
      {people && (
        <FilterBar
          consultants={people.filter((u) => u.role === "consultor")}
          clients={people.filter((u) => u.role === "usuario" && !u.deleted).map((u) => ({ username: u.username, name: u.name, consultant: u.consultant }))}
          value={filter}
          onChange={setFilter}
        />
      )}
      {id === "resumen" && <ConsultantsOverview filter={filter} />}
      {id === "tendencias" && <Insights endpoint="/api/admin/insights" filter={filter} />}
      {id === "avisos" && <ActivityFeed kind="avisos" filter={filter} />}
      {id === "lista" && (
        <>
          <ClientList onOpen={setSelected} filter={filter} />
          <ActivityFeed filter={filter} />
        </>
      )}
    </>
  );
}

function ClientList({ onOpen, filter }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/admin/clients")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudieron cargar los clientes.")));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Cargando clientes...</p>;

  const rows = data.clients.filter((c) => (!filter.client || c.username === filter.client) && (!filter.consultant || c.consultant_username === filter.consultant));
  return (
    <>
      <section className="datil-card">
        <h2>Clientes de Datil Solution</h2>
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
