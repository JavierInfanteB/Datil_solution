import { MODULE_REGISTRY } from "../modules/moduleRegistry";
import { isGranted } from "../utils/permissions";

// Permisos sin pantalla propia en el menú: se usan dentro de otros módulos.
const EXTRA_LABELS = { risk: "Riesgo" };
const findModule = (moduleId) => MODULE_REGISTRY.find((m) => m.id === moduleId);
const moduleLabel = (moduleId) => findModule(moduleId)?.name ?? EXTRA_LABELS[moduleId] ?? moduleId;
const sectionLabel = (moduleId, sectionId) =>
  findModule(moduleId)?.sections?.find((s) => s.id === sectionId)?.name ?? sectionId;

// Matriz de casillas: una fila por usuario o por puesto, una columna por permiso concedible (el módulo,
// o cada una de sus secciones). rows: [{ key, label, granted, inherited }]; `inherited` son los permisos
// que la fila recibe de su puesto: se ven marcados y no se pueden quitar desde aquí.
// onChange(key, permisos) recibe la lista completa que debe quedar guardada para esa fila.
export default function PermissionMatrix({ modules, rows, onChange, disabled, actions, nameHeader = "Nombre" }) {
  const columns = modules.flatMap((mod) =>
    mod.sections.length
      ? mod.sections.map((s) => ({ moduleId: mod.id, perm: `${mod.id}.${s}` }))
      : [{ moduleId: mod.id, perm: mod.id }]
  );

  const toggle = (row, column) => {
    const mod = modules.find((m) => m.id === column.moduleId);
    // Un módulo concedido completo ("trading") se abre en sus secciones para poder quitar solo una.
    const leaves = row.granted.flatMap((p) =>
      p === mod.id && mod.sections.length ? mod.sections.map((s) => `${mod.id}.${s}`) : [p]
    );
    const next = isGranted(row.granted, column.perm)
      ? leaves.filter((p) => p !== column.perm)
      : [...leaves, column.perm];
    onChange(row.key, next);
  };

  return (
    <div className="datil-table-wrap">
      <table className="datil-table">
        <thead>
          <tr>
            <th rowSpan={2}>{nameHeader}</th>
            {modules.map((mod) => (
              <th
                key={mod.id}
                colSpan={mod.sections.length || 1}
                rowSpan={mod.sections.length ? 1 : 2}
                className={mod.sections.length ? "datil-th-group" : undefined}
              >
                {moduleLabel(mod.id)}
              </th>
            ))}
            {actions && <th rowSpan={2} />}
          </tr>
          <tr>
            {modules.flatMap((mod) =>
              mod.sections.map((s) => <th key={`${mod.id}.${s}`}>{sectionLabel(mod.id, s)}</th>)
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              {columns.map((column) => {
                const inherited = isGranted(row.inherited ?? [], column.perm);
                return (
                  <td key={column.perm}>
                    <input
                      type="checkbox"
                      aria-label={`${row.key}: ${column.perm}`}
                      title={inherited ? "Viene de su puesto" : undefined}
                      disabled={disabled || inherited}
                      checked={inherited || isGranted(row.granted, column.perm)}
                      onChange={() => toggle(row, column)}
                    />
                  </td>
                );
              })}
              {actions && <td>{actions(row)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
