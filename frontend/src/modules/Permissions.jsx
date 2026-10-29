import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { isGranted } from "../utils/permissions";
import { MODULE_REGISTRY } from "./moduleRegistry";

// Permisos sin pantalla propia en el menú: se usan dentro de otros módulos.
const EXTRA_LABELS = { risk: "Riesgo" };
const findModule = (moduleId) => MODULE_REGISTRY.find((m) => m.id === moduleId);
const moduleLabel = (moduleId) => findModule(moduleId)?.name ?? EXTRA_LABELS[moduleId] ?? moduleId;
const sectionLabel = (moduleId, sectionId) =>
  findModule(moduleId)?.sections?.find((s) => s.id === sectionId)?.name ?? sectionId;

export default function Permissions() {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [savingUser, setSavingUser] = useState(null);

  const load = () => {
    apiClient
      .get("/api/permissions")
      .then(({ data }) => setInfo(data))
      .catch(() => setError("No tienes acceso a esta sección."));
  };

  useEffect(load, []);

  const toggle = (username, column) => {
    const current = info.permissions[username] ?? [];
    const mod = info.modules.find((m) => m.id === column.moduleId);
    // Un módulo concedido completo ("trading") se abre en sus secciones para poder quitar solo una.
    const leaves = current.flatMap((p) =>
      p === mod.id && mod.sections.length ? mod.sections.map((s) => `${mod.id}.${s}`) : [p]
    );
    const next = isGranted(current, column.perm)
      ? leaves.filter((p) => p !== column.perm)
      : [...leaves, column.perm];

    setSavingUser(username);
    apiClient
      .put(`/api/permissions/${username}`, { modules: next })
      .then(load)
      .finally(() => setSavingUser(null));
  };

  if (error) return <p className="datil-error">{error}</p>;
  if (!info) return <p>Cargando permisos...</p>;

  const usernames = Object.keys(info.permissions);
  // Una columna por permiso concedible: el módulo, o cada una de sus secciones.
  const columns = info.modules.flatMap((mod) =>
    mod.sections.length
      ? mod.sections.map((s) => ({ moduleId: mod.id, perm: `${mod.id}.${s}` }))
      : [{ moduleId: mod.id, perm: mod.id }]
  );

  return (
    <section className="datil-card">
      <h2>Gestión de permisos</h2>
      <div className="datil-table-wrap">
        <table className="datil-table">
          <thead>
            <tr>
              <th rowSpan={2}>Usuario</th>
              {info.modules.map((mod) => (
                <th
                  key={mod.id}
                  colSpan={mod.sections.length || 1}
                  rowSpan={mod.sections.length ? 1 : 2}
                  className={mod.sections.length ? "datil-th-group" : undefined}
                >
                  {moduleLabel(mod.id)}
                </th>
              ))}
            </tr>
            <tr>
              {info.modules.flatMap((mod) =>
                mod.sections.map((s) => <th key={`${mod.id}.${s}`}>{sectionLabel(mod.id, s)}</th>)
              )}
            </tr>
          </thead>
          <tbody>
            {usernames.map((username) => (
              <tr key={username}>
                <td>{username}</td>
                {columns.map((column) => (
                  <td key={column.perm}>
                    <input
                      type="checkbox"
                      aria-label={`${username}: ${column.perm}`}
                      disabled={savingUser === username}
                      checked={isGranted(info.permissions[username] ?? [], column.perm)}
                      onChange={() => toggle(username, column)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
