# Asignación de tareas — Datil Solution

Las tareas y los roles se asignaron el **31/10/2026** por WhatsApp, en el mismo grupo donde se compartió el documento "Plan de entregas y Modelo E-R".

Fechas límite (todas a las 8:00 PM): **Entrega 1** sábado 7 de noviembre de 2026, **Entrega 2** sábado 14 de noviembre de 2026. La auditoría del frontend (Luna) es un entregable final, a unos 15 días: **domingo 22 de noviembre de 2026**.

## Equipo y rol

| Integrante | Rol |
|---|---|
| Héctor Guerrero | Ciberseguridad |
| Javier Infante | Backend |
| Luna Acosta | Frontend |
| Paulina Muciño Hernández | Base de datos |
| Nikole Calderón | Base de datos |
| Nate | Automatizaciones |
| Carlos Vences | Project Manager / BA |

## Tareas

| Entrega | Qué | Responsable |
|---|---|---|
| 1 (7 nov) | Ideas de implementación de alertas (medios de envío, costos, disparadores, preferencias del cliente) | Nate |
| 1 (7 nov) | Misión, visión y documentación de identidad (objetivos, motivaciones, origen, necesidades, versión corta para la web) | Carlos |
| 2 (14 nov) | Modelo entidad-relación (27 tablas, 6 grupos) | Paulina (grupos A a C) y Nikole (grupos D a F) |
| 2 (14 nov) | Modelo relacional (tipos, PK, FK, restricciones, 3FN) | Paulina y Nikole, sobre los grupos que dibujó cada una |
| 2 (14 nov) | Sugerencias de seguridad con documentación de implementación y funcionamiento | Héctor |
| 2 (14 nov) | Modelo de IA en la nube respondiendo con la documentación | Nate |
| Final (22 nov) | Auditoría del frontend y propuesta de mejoras, documentadas (ver sección "Frontend: auditoría y mejoras") | Luna |
| 2 (14 nov) | Documentación del proyecto y reparto de la exposición | Carlos |
| 2 (14 nov) | Documentación técnica (arquitectura, base de datos, despliegue) | Por confirmar (propuesta: Javier) |

## Frontend: auditoría y mejoras (Luna)

**Objetivo:** documentar cómo está armado el frontend y proponer mejoras para que la plataforma sea más fácil de entender y de usar, tanto para el cliente como para el consultor.

**Qué se revisa** (React + Vite, en `frontend/src`):

| Área | Dónde | Qué se documenta |
|---|---|---|
| Estructura | `App.jsx`, `pages/`, `modules/` (Portfolio, Trading, Plan, Avisos, Consultor, AdminClients, Permissions) | Mapa de pantallas, quién ve qué según rol y permisos, navegación |
| Componentes | `components/` (24 componentes: alertas, riesgo, gráficas, reportes, administración) | Para qué sirve cada uno, dónde se repite lógica, cuáles son muy largos (el mayor, `SignalsFeed.jsx`, ronda las 235 líneas) |
| Estado y sesión | `contexts/`, `ProtectedRoute.jsx`, `SessionWarning.jsx` | Cómo se guarda la sesión, avisos de expiración, relación con las sugerencias de seguridad de Héctor |
| Lógica de apoyo | `utils/` (riesgo, variación, permisos, reinversión, formato) | Qué calcula cada función, ejemplos de entrada y salida, qué tiene pruebas y qué no |
| Estilo | `index.css`, `App.css`, `styles/datil-theme.css`, `ThemeContext.jsx` | Colores, tipografía y tema claro/oscuro; estilos duplicados |
| Conexión con el backend | `api/client.js` | Qué endpoints consume cada pantalla y cómo se manejan los errores |

**Qué se busca mejorar** (criterios de la propuesta):

1. **Claridad para el usuario:** textos sin jerga financiera, explicación corta del riesgo y de cada alerta, estados vacíos y mensajes de error entendibles.
2. **Funciones más digeribles:** partir los componentes largos, nombrar mejor las funciones, quitar lógica repetida y dejar comentarios solo donde el porqué no se ve.
3. **Flujos más cortos:** menos clics para las tareas frecuentes (ver cartera, comprar o vender, revisar alertas).
4. **Accesibilidad y responsivo:** contraste, navegación con teclado, etiquetas en formularios y uso en teléfono.
5. **Pruebas:** hoy solo `permissions` y `variation` tienen; proponer cuáles faltan primero (riesgo, reinversión, formato).

**Entregable:** un documento con (a) el mapa del frontend, (b) la lista de hallazgos con prioridad alta, media o baja, (c) cada mejora propuesta con el antes y el después, y (d) un orden sugerido de implementación. Se coordina con Héctor (pantallas de seguridad), Nate (avisos de alertas) y Javier (endpoints).

## Exposición (propuesta)

| Tema | Quién |
|---|---|
| Introducción y origen de la empresa | Carlos |
| Modelo E-R y relacional | Paulina y Nikole |
| Seguridad | Héctor |
| Alertas y modelo de IA en la nube | Nate |
| Auditoría y mejoras del frontend | Luna |

## Estado

- Backend (Javier): su parte ya está hecha.
- Entrega 1: vencida el 7 de nov a las 8:00 PM; Nate y Carlos pendientes de subir.
