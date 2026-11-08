import { useMemo, useState } from "react";

// Franja de "quién necesita atención" para listas de clientes (consultor y admin): un resumen en una frase, tarjetas con
// conteos que filtran al tocarlas, búsqueda por nombre y orden. No pide nada al servidor: trabaja sobre las filas que ya
// tiene la pantalla. `tags`: [{id, label, attention?, test(row)}], `sorts`: [{id, label, cmp(a, b)}].
export function useTriage(rows, { tags, sorts, searchText }) {
  const [search, setSearch] = useState("");
  const [active, setActive] = useState(null);
  const [sortId, setSortId] = useState(sorts[0].id);

  const counts = useMemo(() => Object.fromEntries(tags.map((t) => [t.id, rows.filter(t.test).length])), [rows, tags]);
  const visible = useMemo(() => {
    const text = search.trim().toLowerCase();
    const tag = tags.find((t) => t.id === active);
    const sort = sorts.find((s) => s.id === sortId);
    return rows
      .filter((r) => (!tag || tag.test(r)) && (!text || searchText(r).toLowerCase().includes(text)))
      .sort(sort.cmp);
  }, [rows, tags, sorts, searchText, search, active, sortId]);

  const clear = () => {
    setSearch("");
    setActive(null);
  };
  return { search, setSearch, active, setActive, sortId, setSortId, counts, visible, total: rows.length, clear };
}

export default function ClientTriage({ triage, tags, sorts, title = "¿Quién necesita atención?" }) {
  const { search, setSearch, active, setActive, sortId, setSortId, counts, visible, total, clear } = triage;
  const pending = tags.filter((t) => t.attention && counts[t.id] > 0);
  const filtered = Boolean(search || active);

  return (
    <section className="datil-card datil-triage" aria-label={title}>
      <h2>{title}</h2>
      <p className="datil-triage-headline">
        {pending.length === 0 ? (
          "Todo en orden: ningún cliente necesita atención ahora."
        ) : (
          <>
            Atención: {pending.map((t, i) => (
              <span key={t.id}>
                {i > 0 && " · "}
                <strong>{counts[t.id]}</strong> {t.short ?? t.label.toLowerCase()}
              </span>
            ))}
            .
          </>
        )}
      </p>

      <div className="datil-triage-cards" role="group" aria-label="Filtrar por situación">
        {tags.map((t) => {
          const n = counts[t.id];
          const on = active === t.id;
          const cls = ["datil-triage-card", on && "active", t.attention && n > 0 && "warn", n === 0 && "empty"].filter(Boolean).join(" ");
          return (
            <button key={t.id} type="button" className={cls} aria-pressed={on} onClick={() => setActive(on ? null : t.id)}>
              <strong>{n}</strong>
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      <div className="datil-triage-tools">
        <input type="search" className="datil-search-input" placeholder="Buscar por nombre o usuario" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Buscar cliente" />
        <label className="datil-triage-sort">
          Ordenar por
          <select value={sortId} onChange={(e) => setSortId(e.target.value)}>
            {sorts.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <span className="datil-period-tag" aria-live="polite">
          Mostrando {visible.length} de {total}
        </span>
        {filtered && (
          <button type="button" className="datil-link" onClick={clear}>
            Quitar filtros
          </button>
        )}
      </div>
    </section>
  );
}
