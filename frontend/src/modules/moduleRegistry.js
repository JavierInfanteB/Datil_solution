import Portfolio from "./Portfolio";
import Trading from "./Trading";
import Permissions from "./Permissions";

// Catalogo de modulos instalados en el index. Agregar uno nuevo = una entrada
// aqui + su blueprint en el backend + el string de permiso correspondiente.
// El index nunca decide "quien ve que": solo filtra este catalogo contra los
// permisos que devuelve /api/permissions/me.
export const MODULE_REGISTRY = [
  { id: "portfolio", name: "Mi Cartera", Component: Portfolio, order: 1 },
  { id: "trading", name: "Comprar / Vender", Component: Trading, order: 2 },
  { id: "permissions", name: "Permisos", Component: Permissions, order: 3 },
];

export function getAvailableModules(allowedModuleIds) {
  return MODULE_REGISTRY.filter((mod) => allowedModuleIds.includes(mod.id)).sort(
    (a, b) => a.order - b.order
  );
}
