import { useEffect, useRef, useState } from "react";

// Reemplaza el <select> nativo del navegador (inconsistente entre SO/navegador)
// por un listbox propio con el estilo de la aplicacion.
export default function Select({ value, options, onChange, placeholder = "Selecciona..." }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selected = options.find((opt) => opt.value === value);

  return (
    <div className="datil-select" ref={rootRef}>
      <button
        type="button"
        className="datil-select-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span>{selected ? selected.label : placeholder}</span>
        <span className="datil-select-caret" aria-hidden="true" />
      </button>
      {open && (
        <ul className="datil-select-list" role="listbox">
          {options.map((opt) => (
            <li key={opt.value}>
              <button
                type="button"
                className={opt.value === value ? "datil-select-option active" : "datil-select-option"}
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
              >
                {opt.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
