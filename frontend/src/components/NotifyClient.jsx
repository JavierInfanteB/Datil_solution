import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { KIND_LABEL } from "../utils/avisos";
import { formatDateTime } from "../utils/format";
import { apiError } from "../utils/risk";
import KindTag from "./KindTag";

const EMPTY = { kind: "aviso", title: "", message: "" };

// Avisar al cliente: el consultor elige el tipo (aviso, riesgo o acción sugerida), escribe y envía; abajo ve
// lo que ya mandó y si el cliente lo leyó. `draft` precarga el formulario desde una decisión sugerida.
export default function NotifyClient({ username, draft, hideSent = false, embedded = false, onSent }) {
  const [form, setForm] = useState(EMPTY);
  const [sent, setSent] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const url = `/api/consultant/clients/${username}/notifications`;

  const loadSent = () =>
    apiClient
      .get(url)
      .then(({ data }) => setSent(data))
      .catch(() => setSent([]));

  useEffect(() => {
    loadSent();
  }, [username]);

  useEffect(() => {
    if (draft) setForm({ kind: draft.kind, title: draft.title, message: draft.message });
  }, [draft]);

  const field = (name) => ({ value: form[name], onChange: (e) => setForm({ ...form, [name]: e.target.value }) });

  const send = (e) => {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    apiClient
      .post(url, form)
      .then(() => {
        setMessage({ ok: true, text: "Aviso enviado." });
        setForm(EMPTY);
        onSent?.();
        return loadSent();
      })
      .catch((err) => setMessage({ ok: false, text: apiError(err, "No se pudo enviar el aviso.") }))
      .finally(() => setBusy(false));
  };

  const Wrap = embedded ? "div" : "section";
  return (
    <Wrap className={embedded ? undefined : "datil-card"}>
      {!embedded && <h2>Avisar al cliente</h2>}
      <form onSubmit={send}>
        <div className="datil-form-row">
          <label>
            Tipo
            <select {...field("kind")}>
              {Object.entries(KIND_LABEL).map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="datil-field-wide">
            Título
            <input {...field("title")} required maxLength={80} />
          </label>
        </div>
        <div className="datil-form-row">
          <label className="datil-field-wide">
            Mensaje
            <textarea {...field("message")} required maxLength={1000} rows={4} />
          </label>
        </div>
        <div className="datil-actions">
          <button className="datil-btn datil-btn-primary" disabled={busy}>
            Enviar aviso
          </button>
        </div>
      </form>
      {message && <p className={message.ok ? "datil-success" : "datil-error"}>{message.text}</p>}

      {!hideSent && sent && sent.length > 0 && (
        <>
          <h3 className="datil-subheading">Avisos enviados</h3>
          <div className="datil-table-wrap">
            <table className="datil-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>Título</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {sent.map((n) => (
                  <tr key={n.id}>
                    <td>{formatDateTime(n.date)}</td>
                    <td>
                      <KindTag kind={n.kind} />
                    </td>
                    <td>{n.title}</td>
                    <td>{n.read ? "Leído" : "Sin leer"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Wrap>
  );
}
