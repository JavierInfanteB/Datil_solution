// Un dátil (la fruta) con barras de datos dentro. Es el mismo dibujo que public/favicon.svg.
export default function Logo() {
  return (
    <svg className="datil-logo" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="currentColor" />
      <g transform="rotate(28 16 17)" fill="#14161c">
        <ellipse cx="16" cy="17" rx="7" ry="11" />
        <path d="M16 6.2c0-2 1.2-3 3-3.2" stroke="#14161c" strokeWidth="1.8" fill="none" strokeLinecap="round" />
      </g>
      <g fill="currentColor">
        <rect x="12" y="18" width="2.2" height="3.5" rx=".6" />
        <rect x="15" y="15" width="2.2" height="6.5" rx=".6" />
        <rect x="18" y="12" width="2.2" height="9.5" rx=".6" />
      </g>
    </svg>
  );
}
