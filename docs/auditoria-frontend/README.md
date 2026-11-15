# Auditoría del frontend — Datil Solution

Entregable final de frontend (ver `docs/Asignacion-de-tareas.md`, sección "Frontend: auditoría y mejoras").
Alcance: `frontend/src` (React + Vite). Las capturas de antes y después están en `capturas/antes` y `capturas/despues`
(prefijo `d-` = escritorio 1366 px, `m-` = celular 390 px).

## a) Mapa del frontend

| Sección del menú | Módulo | Subsecciones | Quién la ve |
|---|---|---|---|
| Mi Cartera | `modules/Portfolio.jsx` | — | Usuario (cliente) |
| Comprar / Vender | `modules/Trading.jsx` | Acciones · Bonos y CETES | Usuario; admin en nombre de un cliente |
| Mi plan | `modules/Plan.jsx` | Alertas · Metas · Notas para mi consultor · Reporte | Usuario |
| Mis clientes | `modules/Consultor.jsx` | Clientes · Sugerencias y alertas · Tendencias · Avisos | Consultor |
| Clientes de Datil | `modules/AdminClients.jsx` | Ganancias y pérdidas · Clientes y operaciones · Tendencias · Avisos | Admin |
| Usuarios y permisos | `modules/Permissions.jsx` | — | Admin |
| Avisos | `modules/Avisos.jsx` | — | Todos |

- El menú se arma con `modules/moduleRegistry.js` según los permisos que regresa el backend; `pages/DashboardPage.jsx` monta el módulo activo.
- Sesión: `contexts/AuthContext.jsx` (token y usuario en `localStorage`), `components/ProtectedRoute.jsx` y `components/SessionWarning.jsx` (aviso antes de expirar).
- Backend: todo pasa por `api/client.js` (axios). Los errores se convierten en texto con `utils/errors.js`.
- Lógica sin interfaz en `utils/`: formato, riesgo, variación, permisos, reinversión, avisos y glosario.
- Componentes más largos: `Trading.jsx` (≈490 líneas), `Consultor.jsx` (≈365), `Presentacion.jsx` (≈320) y `SignalsFeed.jsx` (≈235).

## b) Hallazgos

| # | Hallazgo | Prioridad | Estado |
|---|---|---|---|
| 1 | Un dato vacío (N/D) se pintaba de verde porque `null >= 0` es verdadero en JavaScript. La regla verde/rojo estaba copiada en unos 10 archivos. | Alta | Corregido |
| 2 | Comprar / Vender: un doble clic podía mandar la misma orden dos veces. | Alta | Corregido |
| 3 | Si se cambiaba rápido de activo, el histórico anterior podía llegar tarde y sobrescribir al nuevo. | Media | Corregido |
| 4 | Un dato dañado en `localStorage` dejaba la página en blanco al abrirla. | Media | Corregido |
| 5 | Sin servidor o sin internet, el usuario veía "Ocurrió un error" en lugar de saber que no hay conexión. | Media | Corregido |
| 6 | Contraste bajo en texto gris, verde, rojo y dorado sobre blanco (menor a 4.5:1). | Media | Corregido |
| 7 | Navegación con teclado: no había foco visible, las tablas con scroll no se alcanzaban, los menús no se cerraban con Escape y había columnas sin encabezado. | Media | Corregido |
| 8 | Lectores de pantalla: los errores no se anunciaban, el aviso de sesión no era un diálogo y los menús no tenían roles. | Media | Corregido |
| 9 | Jerga sin explicar: "Beta" y "Var. (pp)". | Media | Corregido (glosario) |
| 10 | En celular, cada cifra del resumen ocupaba un renglón y alargaba mucho la pantalla. | Baja | Corregido |
| 11 | Todo el panel se descargaba al iniciar sesión, aunque el usuario solo abriera una sección. | Baja | Corregido (carga por módulo) |
| 12 | Restos de la plantilla de Vite que nadie usaba: `App.css`, `assets/react.svg`, `assets/vite.svg` y `assets/hero.png`. | Baja | Eliminados |
| 13 | Texto de Bonos dentro del bloque que solo se muestra en Acciones, por lo que nunca aparecía. Incluía las explicaciones de CETES, Bono M, Udibono y BPA. | Baja | Código eliminado; ver pendientes |
| 14 | Faltaban pruebas para formato, errores y catálogos. | Media | 3 archivos de pruebas nuevos |

## c) Mejoras: antes y después

| Mejora | Antes | Después | Archivos |
|---|---|---|---|
| Color de tendencia | `v >= 0 ? "datil-up" : "datil-down"` repetido; N/D salía en verde | `trendClass()` en `utils/format.js`; N/D sin color | `format.js` y 13 pantallas |
| Orden doble | Botón siempre activo | Se desactiva y dice "Enviando..." mientras se procesa | `Trading.jsx` |
| Errores de red | "Ocurrió un error." | "No hay conexión con el servidor. Revisa tu internet e intenta de nuevo." | `utils/errors.js`, `utils/risk.js` |
| Contraste | `--datil-text-muted #6b7280`, `--datil-up #0f7b3c`, `--datil-down #c1272d` | `#5b6270`, `#0b6b34`, `#a81f25` y `--datil-accent-text` para texto dorado | `datil-theme.css` |
| Teclado | Sin foco visible; `outline: none` en campos | `:focus-visible` en todo; tablas con `tabIndex`; Escape cierra los menús | `datil-theme.css`, `Select.jsx`, `StockSearch.jsx`, tablas |
| Lectores de pantalla | Errores como texto plano | `role="alert"`, `role="alertdialog"` en el aviso de sesión, roles de lista y opción, encabezados ocultos "Acciones" | 25 archivos |
| Glosario | "Beta" y "pp" sin explicar | Subrayado punteado con explicación al pasar el cursor o enfocar (`Term.jsx`, `glossary.js`) | `PortfolioRisk`, `StockCompare`, `Trading` |
| Celular | Resumen en 1 columna | Resumen en 2 columnas: Mi cartera pasó de 2726 a 2266 px de alto y Reporte de 1427 a 1185 px | `datil-theme.css`, `estilo-gbm.css` |
| Carga | Los 7 módulos en el paquete inicial | `React.lazy` + `Suspense` por módulo | `moduleRegistry.js`, `DashboardPage.jsx` |
| Mensaje sin módulos | "No tienes módulos habilitados todavía." | Además indica pedir permisos al administrador | `DashboardPage.jsx` |

Capturas de referencia: `m-usuario-mi-cartera.png` y `m-usuario-mi-plan-reporte.png` muestran el cambio más visible. En escritorio, las diferencias son de color y foco, y casi no se notan a simple vista.

## d) Orden sugerido para lo que falta

1. **Volver a mostrar la explicación de cada bono en Comprar / Vender.** Los textos de CETES, Bono M, Udibono y BPA (por ejemplo "vale 100 UDIS por título…") existían, pero nunca se veían. Conviene ponerlos junto a la cotización de Bonos y CETES.
2. **Partir los componentes largos**, empezando por `Trading.jsx` (acciones y bonos en archivos separados), `Consultor.jsx` y `SignalsFeed.jsx`.
3. **Flujos más cortos:** medir clics para ver cartera, comprar o vender y revisar alertas, y proponer accesos directos.
4. **Pruebas que faltan:** cálculos de `utils/risk.js` y `useStockRisk`, y los componentes con más lógica.
5. **Nuevas capturas con datos reales.** Las actuales se tomaron en modo de pruebas sin precios de mercado, por eso varias pantallas muestran "No se pudo valuar alguna acción" o "No se pudo obtener el histórico".
6. Agregar al glosario "Volatilidad" y "Caída máxima": las definiciones ya están en `glossary.js`, pero todavía no se usan en pantalla.

## Verificación

- `npm test`: 30 pruebas, 0 fallas (incluye las nuevas de `format`, `errors` y `catalogos`).
- Pendiente correr `npm run lint` y `npm run build` en una máquina con las dependencias instaladas.
- El parche se aplicó sobre `main` después de integrar las reglas de Banxico (Udibonos y BPA). El único ajuste manual fue el hallazgo 13 en `Trading.jsx`.
