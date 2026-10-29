// "trading" concede el módulo completo y "trading.bono" solo esa sección; pedir el
// módulo pasa con cualquiera de sus secciones. Misma regla que is_granted en el backend.
export function isGranted(granted, perm) {
  const [moduleId] = perm.split(".");
  return granted.includes(moduleId) || granted.includes(perm) || granted.some((p) => p.startsWith(`${perm}.`));
}
