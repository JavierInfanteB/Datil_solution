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
  const onKeyDown = (event) => {
    if (event.key === "Escape") setOpen(false);
  };

  return (
    <div className="datil-select" ref={rootRef} onKeyDown={onKeyDown}>
      <button
        type="button"
        className="datil-select-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span>{selected ? selected.label : placeholder}</span>
        <span className="datil-select-caret" aria-hidden="true" />
      </button>
      {open && (
        <ul className="datil-select-list" role="listbox">
          {options.map((opt) => (
            <li key={opt.value} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={opt.value === value}
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
