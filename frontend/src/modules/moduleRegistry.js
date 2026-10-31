import Portfolio from "./Portfolio";
import Trading from "./Trading";
import Avisos from "./Avisos";
import AdminClients from "./AdminClients";
import Consultor from "./Consultor";
import Plan from "./Plan";
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
  { id: "avisos", name: "Avisos", Component: Avisos, order: 3 },
  {
    id: "plan",
    name: "Mi plan",
    Component: Plan,
    order: 3.5,
    sections: [
      { id: "alertas", name: "Alertas" },
      { id: "metas", name: "Metas" },
      { id: "notas", name: "Notas para mi consultor" },
      { id: "reporte", name: "Reporte" },
    ],
  },
  {
    id: "consultor",
    name: "Mis clientes",
    Component: Consultor,
    order: 4,
    sections: [
      { id: "resumen", name: "Ganancias y pérdidas" },
      { id: "clientes", name: "Clientes" },
      { id: "alertas", name: "Alertas" },
      { id: "sugerencias", name: "Sugerencias" },
      { id: "tendencias", name: "Tendencias" },
    ],
  },
  {
    id: "clientes",
    name: "Clientes de Datil",
    Component: AdminClients,
    order: 4,
    sections: [
      { id: "resumen", name: "Ganancias y pérdidas" },
      { id: "lista", name: "Clientes y operaciones" },
      { id: "tendencias", name: "Tendencias" },
    ],
  },
  { id: "permissions", name: "Usuarios y permisos", Component: Permissions, order: 5 },
];

export function getAvailableModules(granted) {
  return MODULE_REGISTRY.filter((mod) => isGranted(granted, mod.id))
    .map((mod) => ({ ...mod, sections: (mod.sections ?? []).filter((s) => isGranted(granted, `${mod.id}.${s.id}`)) }))
    .sort((a, b) => a.order - b.order);
}
