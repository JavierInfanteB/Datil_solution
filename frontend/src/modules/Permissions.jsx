import { useEffect, useState } from "react";
import apiClient from "../api/client";
import PermissionMatrix from "../components/PermissionMatrix";
import UsersAdmin from "../components/UsersAdmin";
import { apiError } from "../utils/risk";

const TABS = [
  { id: "usuarios", label: "Usuarios" },
  { id: "puestos", label: "Puestos" },
  { id: "permisos", label: "Permisos por usuario" },
];

// Administración (solo admin): quién es cada quién, los lotes de permisos por puesto y los
// permisos propios de cada usuario. El admin siempre ve todo, por eso no aparece en las matrices.
export default function Permissions() {
  const [tab, setTab] = useState("usuarios");
  const [info, setInfo] = useState(null);
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([apiClient.get("/api/permissions"), apiClient.get("/api/users")])
      .then(([permissions, people]) => {
        setInfo(permissions.data);
        setUsers(people.data);
      })
      .catch(() => setError("No tienes acceso a esta sección."));

  useEffect(() => {
    load();
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!info || !users) return <p>Cargando permisos...</p>;

  const puestos = Object.keys(info.puestos);

  return (
    <section className="datil-card">
      <h2>Usuarios y permisos</h2>
      <div className="datil-lapse-bar" role="group" aria-label="Sección">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={t.id === tab ? "datil-chip active" : "datil-chip"}
            aria-pressed={t.id === tab}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "usuarios" && <UsersAdmin users={users.users} roles={users.roles} puestos={puestos} reload={load} />}
      {tab === "puestos" && <PuestosTab info={info} users={users.users} reload={load} />}
      {tab === "permisos" && <PerUserTab info={info} users={users.users} reload={load} />}
    </section>
  );
}

// Guarda con `request` y recarga; el mensaje de error del servidor se muestra tal cual.
function useSaver(reload) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = (request) => {
    setBusy(true);
    setError("");
    return request()
      .then(reload)
      .catch((err) => setError(apiError(err, "No se pudo guardar.")))
      .finally(() => setBusy(false));
  };
  return { busy, error, save };
}

function PuestosTab({ info, users, reload }) {
  const { busy, error, save } = useSaver(reload);
  const [name, setName] = useState("");
  const url = (puesto) => `/api/permissions/puestos/${encodeURIComponent(puesto)}`;
  const members = (puesto) => users.filter((u) => u.puesto === puesto).length;

  const rows = Object.entries(info.puestos).map(([puesto, granted]) => ({
    key: puesto,
    label: `${puesto} (${members(puesto)})`,
    granted,
  }));

  const create = (e) => {
    e.preventDefault();
    save(() => apiClient.put(url(name.trim()), { modules: [] })).then(() => setName(""));
  };

  return (
    <>
      <p className="datil-period-tag">
        Un puesto es un lote de permisos: cambiarlo cambia a todos los que lo tienen. Entre paréntesis, cuántos usuarios.
      </p>
      <PermissionMatrix
        modules={info.modules}
        rows={rows}
        nameHeader="Puesto"
        disabled={busy}
        onChange={(puesto, modules) => save(() => apiClient.put(url(puesto), { modules }))}
        actions={(row) => (
          <button
            className="datil-btn datil-btn-secondary"
            disabled={busy || members(row.key) > 0}
            title={members(row.key) > 0 ? "Hay usuarios con este puesto" : undefined}
            onClick={() => save(() => apiClient.delete(url(row.key)))}
          >
            Borrar
          </button>
        )}
      />
      {error && <p className="datil-error">{error}</p>}

      <form onSubmit={create}>
        <h3 className="datil-subheading">Nuevo puesto</h3>
        <div className="datil-form-row">
          <label>
            Nombre
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={40} />
          </label>
        </div>
        <div className="datil-actions">
          <button className="datil-btn datil-btn-primary" disabled={busy}>
            Crear puesto
          </button>
        </div>
      </form>
    </>
  );
}

function PerUserTab({ info, users, reload }) {
  const { busy, error, save } = useSaver(reload);

  const rows = users
    .filter((u) => u.role !== "admin")
    .map((u) => ({
      key: u.username,
      label: u.name,
      granted: info.permissions[u.username] ?? [],
      inherited: info.puestos[u.puesto] ?? [],
    }));

  if (rows.length === 0) return <p className="datil-period-tag">Aún no hay usuarios además del administrador.</p>;

  return (
    <>
      <p className="datil-period-tag">
        Permisos propios de cada usuario, además de los de su puesto. Las casillas marcadas y bloqueadas vienen del puesto.
      </p>
      <PermissionMatrix
        modules={info.modules}
        rows={rows}
        nameHeader="Usuario"
        disabled={busy}
        onChange={(username, modules) => save(() => apiClient.put(`/api/permissions/${username}`, { modules }))}
      />
      {error && <p className="datil-error">{error}</p>}
    </>
  );
}
