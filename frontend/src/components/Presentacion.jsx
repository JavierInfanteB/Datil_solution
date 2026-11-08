import LoginForm from "./LoginForm";
import Logo from "./Logo";
import "../styles/presentacion.css";

// Iconos dibujados a mano (trazo de 1.6 en una cuadrícula de 32): sin librería ni imágenes.
const ico = { viewBox: "0 0 32 32", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };

const Icons = {
  vision: (
    <svg {...ico}>
      <path d="M3 16s5-9 13-9 13 9 13 9-5 9-13 9S3 16 3 16Z" />
      <circle cx="16" cy="16" r="4.5" />
      <path d="M16 13.5v5M13.5 16h5" opacity=".5" />
    </svg>
  ),
  mision: (
    <svg {...ico}>
      <path d="M8 28V4" />
      <path d="M8 6h16l-4 5.5L24 17H8" />
      <circle cx="8" cy="28" r="1.4" fill="currentColor" />
    </svg>
  ),
  objetivos: (
    <svg {...ico}>
      <circle cx="16" cy="16" r="12" />
      <circle cx="16" cy="16" r="7" />
      <circle cx="16" cy="16" r="2" fill="currentColor" />
      <path d="M16 16 27 5M23 5h4v4" />
    </svg>
  ),
  proyectos: (
    <svg {...ico}>
      <rect x="4" y="5" width="24" height="22" rx="3" />
      <path d="M4 11h24M11 5v22" opacity=".5" />
      <path d="M15 17l3 3 6-6" />
    </svg>
  ),
  datos: (
    <svg {...ico}>
      <ellipse cx="14" cy="8" rx="9" ry="3.5" />
      <path d="M5 8v8c0 1.9 4 3.5 9 3.5M5 16v8c0 1.9 4 3.5 9 3.5" />
      <path d="M23 8v6" />
      <circle cx="23" cy="22" r="5" />
      <path d="m20.6 22 1.7 1.7 3.2-3.4" />
    </svg>
  ),
  backend: (
    <svg {...ico}>
      <rect x="4" y="5" width="24" height="8" rx="2.5" />
      <rect x="4" y="19" width="24" height="8" rx="2.5" />
      <path d="M9 9h.01M9 23h.01M16 13v6" />
      <path d="M20 9h4M20 23h4" opacity=".5" />
    </svg>
  ),
  frontend: (
    <svg {...ico}>
      <rect x="3" y="5" width="26" height="20" rx="3" />
      <path d="M3 11h26" />
      <path d="M7 8h.01M10 8h.01" />
      <path d="M8 21v-5M13 21v-8M18 21v-3" />
      <path d="M22 21h3" opacity=".5" />
      <path d="M11 28h10" />
    </svg>
  ),
  seguridad: (
    <svg {...ico}>
      <path d="M16 3 5 7v8c0 7 4.6 11.5 11 14 6.4-2.5 11-7 11-14V7L16 3Z" />
      <rect x="11.5" y="14" width="9" height="7" rx="1.8" />
      <path d="M13.5 14v-2a2.5 2.5 0 0 1 5 0v2" />
    </svg>
  ),
  automatizacion: (
    <svg {...ico}>
      <circle cx="16" cy="16" r="4" />
      <path d="M16 4v4M16 24v4M4 16h4M24 16h4M7.5 7.5l2.8 2.8M21.7 21.7l2.8 2.8M24.5 7.5l-2.8 2.8M10.3 21.7l-2.8 2.8" />
    </svg>
  ),
  ia: (
    <svg {...ico}>
      <rect x="7" y="7" width="18" height="18" rx="4" />
      <path d="M12 3v4M20 3v4M12 25v4M20 25v4M3 12h4M3 20h4M25 12h4M25 20h4" opacity=".5" />
      <path d="M12 19l2.2-6 2 4.5 1.3-2.5H21" />
    </svg>
  ),
  cartera: (
    <svg {...ico}>
      <path d="M4 10a3 3 0 0 1 3-3h17v5" />
      <rect x="4" y="10" width="24" height="16" rx="3" />
      <circle cx="22" cy="18" r="1.5" fill="currentColor" />
    </svg>
  ),
  alerta: (
    <svg {...ico}>
      <path d="M8 22V14a8 8 0 0 1 16 0v8l2 3H6l2-3Z" />
      <path d="M13.5 28a2.7 2.7 0 0 0 5 0" />
    </svg>
  ),
  auditoria: (
    <svg {...ico}>
      <path d="M8 3h11l6 6v20H8V3Z" />
      <path d="M19 3v6h6" />
      <path d="M12 15h9M12 19h9M12 23h5" opacity=".5" />
    </svg>
  ),
  asistente: (
    <svg {...ico}>
      <path d="M5 8a3 3 0 0 1 3-3h16a3 3 0 0 1 3 3v11a3 3 0 0 1-3 3H15l-6 5v-5H8a3 3 0 0 1-3-3V8Z" />
      <path d="M11 12h10M11 16h6" opacity=".6" />
    </svg>
  ),
};

const OBJETIVOS = [
  { icono: "cartera", titulo: "Centralización y valoración", texto: "Una vista consolidada del patrimonio: efectivo en MXN, acciones y deuda gubernamental como CETES y Bonos M." },
  { icono: "objetivos", titulo: "Decisiones informadas", texto: "Rendimientos, costos promedio, utilidades realizadas y puntajes de riesgo calculados de forma automática." },
  { icono: "alerta", titulo: "Monitoreo proactivo", texto: "Alertas configurables por variación, precio objetivo, vencimientos y cupones, con sugerencias de diversificación." },
  { icono: "auditoria", titulo: "Seguridad y auditoría", texto: "Roles, permisos granulares, sesiones con expiración y bitácoras de auditoría de cada movimiento." },
  { icono: "asistente", titulo: "Asistencia inteligente acotada", texto: "Un asistente que explica conceptos y consulta la cartera sin emitir asesoría financiera autónoma." },
];

const EQUIPO = [
  { icono: "proyectos", area: "Gestión de proyectos", texto: "Levantamiento de requerimientos, análisis de negocio, planeación por entregas y documentación del proyecto de principio a fin." },
  { icono: "datos", area: "Bases de datos", texto: "Especialistas en limpieza, depuración y normalización: modelo entidad-relación, llaves, restricciones y datos consistentes sin duplicados." },
  { icono: "backend", area: "Backend", texto: "Servicios y reglas de negocio: cálculo de valuación, órdenes, conexión con fuentes de mercado y endpoints confiables." },
  { icono: "frontend", area: "Frontend", texto: "Interfaces claras y accesibles para el cliente y el consultor, en computadora y en teléfono." },
  { icono: "seguridad", area: "Ciberseguridad y control de accesos", texto: "Roles y permisos, protección de sesiones, bloqueo por intentos fallidos y trazabilidad de cada operación." },
  { icono: "ia", area: "Automatización e inteligencia artificial", texto: "Avisos y alertas que salen solos, y un asistente en la nube que responde con la documentación del proyecto." },
];

// Gráfica decorativa del héroe: curva de patrimonio y barras de posiciones. No representa datos reales.
function GraficaHeroe() {
  return (
    <svg className="dl-grafica" viewBox="0 0 480 320" role="img" aria-label="Ilustración de una gráfica de patrimonio con barras de posiciones">
      <defs>
        <linearGradient id="dl-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--datil-accent)" stopOpacity=".35" />
          <stop offset="1" stopColor="var(--datil-accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g className="dl-rejilla" stroke="currentColor" strokeOpacity=".12">
        {[60, 120, 180, 240].map((y) => <line key={y} x1="20" x2="460" y1={y} y2={y} />)}
      </g>
      <g className="dl-barras" fill="currentColor" fillOpacity=".16">
        {[70, 110, 90, 150, 130, 190, 170, 220].map((h, i) => (
          <rect key={i} x={36 + i * 54} y={280 - h} width="30" height={h} rx="8" style={{ animationDelay: `${i * 70}ms` }} />
        ))}
      </g>
      <path className="dl-area" d="M20 240 80 210 140 222 200 170 260 184 320 120 380 132 460 56V280H20Z" fill="url(#dl-area)" />
      <path className="dl-linea" d="M20 240 80 210 140 222 200 170 260 184 320 120 380 132 460 56" fill="none" stroke="var(--datil-accent)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" pathLength="1" />
      <circle className="dl-punto" cx="460" cy="56" r="7" fill="var(--datil-accent)" />
    </svg>
  );
}

// Dona ilustrativa de composición (efectivo, acciones, deuda). Los porcentajes son de ejemplo.
function Dona() {
  const r = 52;
  const c = 2 * Math.PI * r;
  const partes = [
    { pct: 0.2, color: "var(--datil-accent)", nombre: "Efectivo MXN" },
    { pct: 0.45, color: "#5b6cff", nombre: "Acciones" },
    { pct: 0.35, color: "#2bb39a", nombre: "CETES y Bonos M" },
  ];
  let acumulado = 0;
  return (
    <figure className="dl-dona">
      <svg viewBox="0 0 140 140" role="img" aria-label="Ilustración de la composición de una cartera: efectivo, acciones y deuda gubernamental">
        <g transform="rotate(-90 70 70)" fill="none" strokeWidth="18">
          {partes.map((p) => {
            const largo = p.pct * c;
            const el = <circle key={p.nombre} cx="70" cy="70" r={r} stroke={p.color} strokeDasharray={`${largo - 3} ${c - largo + 3}`} strokeDashoffset={-acumulado} strokeLinecap="butt" />;
            acumulado += largo;
            return el;
          })}
        </g>
        <text x="70" y="68" textAnchor="middle" className="dl-dona-num">100%</text>
        <text x="70" y="84" textAnchor="middle" className="dl-dona-sub">de tu patrimonio</text>
      </svg>
      <figcaption>
        <ul>
          {partes.map((p) => (
            <li key={p.nombre}><i style={{ background: p.color }} />{p.nombre}</li>
          ))}
        </ul>
        <small>Ilustración con datos de ejemplo.</small>
      </figcaption>
    </figure>
  );
}

export default function Presentacion() {
  return (
    <div className="dl-pagina">
      <header className="dl-nav">
        <a className="dl-marca" href="#inicio" aria-label="Datil Solutions, inicio">
          <Logo />
          <span>Datil Solutions</span>
        </a>
        <nav aria-label="Principal">
          <a href="#vision">Visión</a>
          <a href="#objetivos">Objetivos</a>
          <a href="#equipo">Equipo</a>
          <a className="dl-pildora" href="#acceso">Iniciar sesión</a>
        </nav>
      </header>

      <main>
        <section className="dl-heroe" id="inicio">
          <div className="dl-heroe-texto">
            <p className="dl-etiqueta">Consultoría y desarrollo tecnológico</p>
            <h1>Decisiones complejas, <span>datos claros</span>.</h1>
            <p className="dl-lead">
              Diseñamos, estructuramos y construimos proyectos tecnológicos a la medida, de principio a fin: datos, automatización e inteligencia artificial en un solo lugar.
            </p>
            <div className="dl-acciones">
              <a className="dl-pildora dl-pildora-grande" href="#acceso">Probar la plataforma</a>
              <a className="dl-enlace" href="#vision">Conocer más <span aria-hidden="true">↓</span></a>
            </div>
          </div>
          <GraficaHeroe />
        </section>

        <section className="dl-seccion" id="vision" aria-labelledby="t-vision">
          <h2 id="t-vision" className="dl-titulo">Quiénes somos</h2>
          <div className="dl-duo">
            <article className="dl-tarjeta dl-tarjeta-oscura">
              <span className="dl-icono">{Icons.vision}</span>
              <h3>Visión</h3>
              <p>
                Consolidarnos como la firma de consultoría y desarrollo tecnológico de referencia, reconocida por transformar cualquier necesidad de negocio, sin importar su complejidad o industria, en ecosistemas digitales robustos, seguros y escalables, donde los datos, la automatización y la inteligencia artificial impulsen decisiones estratégicas con total transparencia y precisión.
              </p>
            </article>
            <article className="dl-tarjeta">
              <span className="dl-icono">{Icons.mision}</span>
              <h3>Misión</h3>
              <p>
                Diseñamos, estructuramos y construimos proyectos tecnológicos a la medida de principio a fin. Acompañamos a organizaciones y usuarios desde la conceptualización y el levantamiento de requerimientos hasta el despliegue en producción, con arquitecturas de datos sólidas, controles de ciberseguridad de alto estándar y asistentes inteligentes que simplifican operaciones complejas y generan valor tangible.
              </p>
            </article>
          </div>
        </section>

        <section className="dl-seccion" id="objetivos" aria-labelledby="t-objetivos">
          <div className="dl-encabezado">
            <h2 id="t-objetivos" className="dl-titulo">Objetivos del proyecto actual</h2>
            <p className="dl-sub">Una plataforma de cartera de inversión que conecta a inversionistas y consultores en un solo lugar.</p>
          </div>
          <div className="dl-objetivos">
            <Dona />
            <ul className="dl-lista-obj">
              {OBJETIVOS.map((o) => (
                <li key={o.titulo}>
                  <span className="dl-icono dl-icono-chico">{Icons[o.icono]}</span>
                  <div>
                    <h3>{o.titulo}</h3>
                    <p>{o.texto}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="dl-seccion" id="equipo" aria-labelledby="t-equipo">
          <div className="dl-encabezado">
            <h2 id="t-equipo" className="dl-titulo">Nuestro equipo</h2>
            <p className="dl-sub">Un equipo multidisciplinario que cubre todas las capas del ciclo de vida del software.</p>
          </div>
          <ul className="dl-equipo">
            {EQUIPO.map((e) => (
              <li key={e.area} className="dl-tarjeta dl-tarjeta-equipo">
                <span className="dl-icono">{Icons[e.icono]}</span>
                <h3>{e.area}</h3>
                <p>{e.texto}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="dl-seccion dl-acceso" id="acceso" aria-labelledby="t-acceso">
          <div className="dl-encabezado">
            <h2 id="t-acceso" className="dl-titulo">Prueba la plataforma</h2>
            <p className="dl-sub">Inicia sesión con una cuenta de prueba para recorrer cada rol.</p>
          </div>
          <LoginForm enfocar={false} />
        </section>
      </main>

      <footer className="dl-pie">
        <span>Datil Solutions</span>
        <span>Construir tecnología segura e inteligente que simplifique decisiones complejas.</span>
      </footer>
    </div>
  );
}
