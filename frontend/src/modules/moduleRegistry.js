import Portfolio from "./Portfolio";
import Trading from "./Trading";
import Consultor from "./Consultor";
import Permissions from "./Permissions";
import { isGranted } from "../utils/permissions";

// Catalogo de modulos instalados en el index. Agregar uno nuevo = una entrada
// aqui + su blueprint en el backend + su id (y secciones) en MODULES de
// backend/modules/permissions.py. Las secciones son las subpestañas que se
// despliegan bajo el modulo en el menu lateral; el componente recibe la activa
// como prop `section`. El index nunca decide "quien ve que": solo filtra este
// catalogo contra los permisos que devuelve /api/permissions/me.
export const MODULE_REGISTRY = [
  { id: "portfolio", name: "Mi Cartera", Component: Portfolio, order: 1 },
  {
    id: "trading",
    name: "Comprar / Vender",
    Component: Trading,
    order: 2,
    sections: [
      { id: "accion", name: "Acciones" },
      { id: "bono", name: "Bonos y CETES" },
    ],
  },
  { id: "consultor", name: "Mis clientes", Component: Consultor, order: 3 },
  { id: "permissions", name: "Usuarios y permisos", Component: Permissions, order: 4 },
];

export function getAvailableModules(granted) {
  return MODULE_REGISTRY.filter((mod) => isGranted(granted, mod.id))
    .map((mod) => ({ ...mod, sections: (mod.sections ?? []).filter((s) => isGranted(granted, `${mod.id}.${s.id}`)) }))
    .sort((a, b) => a.order - b.order);
}
