import { useState } from "react";
import apiClient from "../api/client";
import { apiError } from "../utils/risk";

// Lista de notas con formulario para agregar y botón para quitar. `url` recibe POST y DELETE <url>/<id>;
// `notes` y `reload` vienen del padre. Sin `url` solo se leen.
export default function NotesBox({ notes, url, reload, placeholder }) {
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  const run = (request) =>
    request()
      .then(() => {
        setError("");
        return reload();
      })
      .catch((err) => setError(apiError(err, "No se pudo guardar.")));

  return (
    <>
      {notes.length === 0 && <p className="datil-period-tag">Sin notas.</p>}
      <ul className="datil-suggestions">
        {notes.map((n) => (
          <li key={n.id}>
            <span className="datil-period-tag">{n.date.slice(0, 10)} </span>
            {n.text}
            {url && (
              <>
                {" "}
                <button className="datil-link" onClick={() => run(() => apiClient.delete(`${url}/${n.id}`))}>
                  Quitar
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      {url && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(() => apiClient.post(url, { text })).then(() => setText(""));
          }}
        >
          <label>
            Nueva nota
            <textarea value={text} onChange={(e) => setText(e.target.value)} required maxLength={1000} rows={3} placeholder={placeholder} />
          </label>
          <div className="datil-actions">
            <button className="datil-btn datil-btn-primary">Guardar nota</button>
          </div>
        </form>
      )}
      {error && <p className="datil-error" role="alert">{error}</p>}
    </>
  );
}
