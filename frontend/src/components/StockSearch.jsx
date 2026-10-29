import { useEffect, useRef, useState } from "react";
import apiClient from "../api/client";

// Autocompletado de acciones/ETFs contra Yahoo Finance: no hay catalogo fijo,
// cualquier simbolo que la API reconozca se puede elegir.
export default function StockSearch({ onSelect, placeholder = "Buscar por nombre o símbolo..." }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      apiClient
        .get("/api/trading/search", { params: { q: query.trim() } })
        .then(({ data }) => setResults(data))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 350);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  return (
    <div className="datil-select" ref={rootRef}>
      <input
        className="datil-search-input"
        value={query}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && (query.trim().length >= 2) && (
        <ul className="datil-select-list" role="listbox">
          {loading && <li className="datil-select-empty">Buscando...</li>}
          {!loading && results.length === 0 && (
            <li className="datil-select-empty">Sin resultados</li>
          )}
          {!loading &&
            results.map((asset) => (
              <li key={asset.symbol}>
                <button
                  type="button"
                  className="datil-select-option"
                  onClick={() => {
                    onSelect(asset);
                    setQuery(`${asset.symbol} - ${asset.name}`);
                    setOpen(false);
                  }}
                >
                  <strong>{asset.symbol}</strong>
                  <span className="datil-select-option-detail">
                    {asset.name} · {asset.exchange}
                    {asset.sector ? ` · ${asset.sector}` : ""}
                  </span>
                </button>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
