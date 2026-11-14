import { useState } from "react";
import apiClient from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { apiError } from "../utils/risk";

const ROLE_LABEL = { usuario: "Usuario", consultor: "Consultor", admin: "Administrador" };
const EMPTY_FORM = { username: "", name: "", password: "", role: "usuario", puesto: "" };

// Alta de usuarios y asignación de rol, puesto y consultor. Los usuarios se asignan a un consultor;
// de momento un consultor solo atiende usuarios, no a otros consultores.
export default function UsersAdmin({ users, puestos, roles, reload }) {
  const { user: me } = useAuth();
  const [form, setForm] = useState(EMPTY_FORM);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  const consultants = users.filter((u) => u.role === "consultor");

  const run = (request, okText) => {
    setBusy(true);
    setMessage(null);
    return request()
      .then(() => {
        setMessage({ ok: true, text: okText });
        return reload();
      })
      .catch((err) => setMessage({ ok: false, text: apiError(err, "No se pudo guardar el cambio.") }))
      .finally(() => setBusy(false));
  };

  // Cambia la contraseña de un usuario: se pide con prompt para no dejar un campo más en la tabla.
  const resetPassword = (u) => {
    const password = window.prompt(`Nueva contraseña para ${u.username} (mín. 8 caracteres)`);
    if (password) run(() => apiClient.patch(`/api/users/${u.username}`, { password }), `Contraseña de ${u.username} cambiada.`);
  };

  const remove = (u) => {
    if (window.confirm(`Dar de baja a ${u.username}? Solo se puede si está en cero. Puedes reactivarlo después.`))
      run(() => apiClient.delete(`/api/users/${u.username}`), `${u.username} dado de baja.`);
  };

  const update = (username, change) => run(() => apiClient.patch(`/api/users/${username}`, change), "Cambio guardado.");

  const create = (e) => {
    e.preventDefault();
    run(() => apiClient.post("/api/users", { ...form, puesto: form.puesto || null }), `Usuario ${form.username} creado.`).then(
      () => setForm(EMPTY_FORM)
    );
  };

  const field = (name) => ({ value: form[name], onChange: (e) => setForm({ ...form, [name]: e.target.value }) });

  return (
    <>
      <form onSubmit={create}>
        <h3 className="datil-subheading">Nuevo usuario</h3>
        <div className="datil-form-row">
          <label>
            Usuario
            <input {...field("username")} required minLength={3} maxLength={32} autoComplete="off" />
          </label>
          <label>
            Nombre
            <input {...field("name")} required autoComplete="off" />
          </label>
          <label>
            Contraseña (mín. 8)
            <input type="password" {...field("password")} required minLength={8} autoComplete="new-password" />
          </label>
          <label>
            Rol
            <select {...field("role")}>
              {roles.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Puesto
            <select {...field("puesto")}>
              <option value="">Sin puesto</option>
              {puestos.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="datil-actions">
          <button className="datil-btn datil-btn-primary" disabled={busy}>
            Crear usuario
          </button>
        </div>
      </form>

      {message && <p className={message.ok ? "datil-success" : "datil-error"}>{message.text}</p>}

      <h3 className="datil-subheading">Usuarios</h3>
      <div className="datil-table-wrap" tabIndex={0}>
        <table className="datil-table">
          <thead>
            <tr>
              <th>Usuario</th>
              <th>Rol</th>
              <th>Puesto</th>
              <th>Consultor asignado</th>
              <th>Cuenta</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username}>
                <td>
                  <strong>{u.name}</strong>
                  <span className="datil-period-tag"> {u.username}</span>
                </td>
                <td>
                  <select
                    aria-label={`Rol de ${u.username}`}
                    value={u.role}
                    disabled={busy || u.username === me.username}
                    onChange={(e) => update(u.username, { role: e.target.value })}
                  >
                    {roles.map((r) => (
                      <option key={r} value={r}>
                        {ROLE_LABEL[r]}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    aria-label={`Puesto de ${u.username}`}
                    value={u.puesto ?? ""}
                    disabled={busy}
                    onChange={(e) => update(u.username, { puesto: e.target.value })}
                  >
                    <option value="">Sin puesto</option>
                    {puestos.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </td>
                <td>
                  {u.role === "usuario" ? (
                    <select
                      aria-label={`Consultor de ${u.username}`}
                      value={u.consultant ?? ""}
                      disabled={busy}
                      onChange={(e) => update(u.username, { consultant: e.target.value })}
                    >
                      <option value="">Sin consultor</option>
                      {consultants.map((c) => (
                        <option key={c.username} value={c.username}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="datil-period-tag">
                      {u.role === "consultor" ? `${users.filter((x) => x.consultant === u.username).length} cliente(s)` : "N/A"}
                    </span>
                  )}
                </td>
                <td>
                  <button className="datil-btn datil-btn-secondary" disabled={busy} onClick={() => resetPassword(u)}>
                    Cambiar contraseña
                  </button>{" "}
                  <button
                    className="datil-btn datil-btn-secondary"
                    disabled={busy || u.username === me.username}
                    onClick={() => update(u.username, { disabled: !u.disabled })}
                  >
                    {u.disabled ? "Reactivar" : "Suspender"}
                  </button>{" "}
                  {!u.disabled && (
                    <button className="datil-btn datil-btn-secondary" disabled={busy || u.username === me.username} onClick={() => remove(u)}>
                      Dar de baja
                    </button>
                  )}
                  {u.deleted && <span className="datil-period-tag"> dado de baja</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
