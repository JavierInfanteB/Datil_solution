// Filtros de pantalla: por consultor (solo el admin) y por cliente. `value` es {consultant, client}; vacío = todos.
// Al cambiar de consultor se suelta el cliente si no es suyo. `clients`: [{username, name, consultant}].
export default function FilterBar({ consultants, clients, value, onChange }) {
  const visible = clients.filter((c) => !value.consultant || c.consultant === value.consultant);
  const set = (change) => {
    const next = { ...value, ...change };
    const own = clients.find((c) => c.username === next.client);
    onChange(own && next.consultant && own.consultant !== next.consultant ? { ...next, client: "" } : next);
  };
  return (
    <div className="datil-filter-bar">
      {consultants && (
        <label>
          Consultor
          <select value={value.consultant} onChange={(e) => set({ consultant: e.target.value })}>
            <option value="">Todos los consultores</option>
            {consultants.map((c) => (
              <option key={c.username} value={c.username}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Cliente
        <select value={value.client} onChange={(e) => set({ client: e.target.value })}>
          <option value="">Todos los clientes</option>
          {visible.map((c) => (
            <option key={c.username} value={c.username}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
