import { useEffect, useState } from "react";
import apiClient from "../api/client";

export default function Permissions() {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [savingUser, setSavingUser] = useState(null);

  const load = () => {
    apiClient
      .get("/api/permissions")
      .then(({ data }) => setInfo(data))
      .catch(() => setError("No tienes acceso a esta seccion."));
  };

  useEffect(load, []);

  const toggleModule = (username, moduleId) => {
    const current = info.permissions[username] ?? [];
    const next = current.includes(moduleId)
      ? current.filter((m) => m !== moduleId)
      : [...current, moduleId];

    setSavingUser(username);
    apiClient
      .put(`/api/permissions/${username}`, { modules: next })
      .then(load)
      .finally(() => setSavingUser(null));
  };

  if (error) return <p className="datil-error">{error}</p>;
  if (!info) return <p>Cargando permisos...</p>;

  const usernames = Object.keys(info.permissions);

  return (
    <section className="datil-card">
      <h2>Gestion de permisos</h2>
      <table className="datil-table">
        <thead>
          <tr>
            <th>Usuario</th>
            {info.available_modules.map((mod) => (
              <th key={mod}>{mod}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {usernames.map((username) => (
            <tr key={username}>
              <td>{username}</td>
              {info.available_modules.map((mod) => (
                <td key={mod}>
                  <input
                    type="checkbox"
                    disabled={savingUser === username}
                    checked={(info.permissions[username] ?? []).includes(mod)}
                    onChange={() => toggleModule(username, mod)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
