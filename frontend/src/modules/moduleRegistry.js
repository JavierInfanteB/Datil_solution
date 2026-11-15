import { lazy } from "react";
import { isGranted } from "../utils/permissions";

// Cada módulo se descarga solo cuando alguien lo abre: quien aún no inicia sesión no baja las gráficas ni el panel.
const Portfolio = lazy(() => import("./Portfolio"));
const Trading = lazy(() => import("./Trading"));
const Avisos = lazy(() => import("./Avisos"));
const AdminClients = lazy(() => import("./AdminClients"));
const Consultor = lazy(() => import("./Consultor"));
const Plan = lazy(() => import("./Plan"));
const Permissions = lazy(() => import("./Permissions"));

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
  { id: "avisos", name: "Avisos", Component: Avisos, order: 6 },
  {
    id: "plan",
    name: "Mi plan",
    Component: Plan,
    order: 3,
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
      { id: "clientes", name: "Clientes" },
      { id: "sugerencias", name: "Sugerencias y alertas" },
      { id: "tendencias", name: "Tendencias" },
      { id: "avisos", name: "Avisos" },
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
      { id: "avisos", name: "Avisos" },
    ],
  },
  { id: "permissions", name: "Usuarios y permisos", Component: Permissions, order: 5 },
];

export function getAvailableModules(granted) {
  return MODULE_REGISTRY.filter((mod) => isGranted(granted, mod.id))
    .map((mod) => ({ ...mod, sections: (mod.sections ?? []).filter((s) => isGranted(granted, `${mod.id}.${s.id}`)) }))
    .sort((a, b) => a.order - b.order);
}
