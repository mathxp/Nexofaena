import './LogoNexoFaena.css';

// Logo oficial (ver docs/marca/logo-nexofaena-sgi.png), versión "fondo
// oscuro": hexágono blanco con la N celeste. Va como SVG inline y no como
// imagen para que se vea nítido en cualquier tamaño y respete la fuente.
export const MarcaNexoFaena = ({ className = '' }) => (
  <svg className={`nx-marca ${className}`} viewBox="0 0 100 100" aria-hidden="true">
    <polygon
      points="50,10 84.64,30 84.64,70 50,90 15.36,70 15.36,30"
      fill="none" stroke="currentColor" strokeWidth="7" strokeLinejoin="round"
    />
    <path
      d="M36 65V36L64 64V35"
      fill="none" stroke="var(--brand-light)" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round"
    />
    <circle cx="36" cy="65.5" r="6.5" fill="currentColor" />
    <circle cx="64" cy="34.5" r="6.5" fill="currentColor" />
  </svg>
);

const LogoNexoFaena = ({ tamano = 'md', conBajada = false, bajada = 'SGI · Trazabilidad de pañol', className = '' }) => (
  <div className={`nx-logo nx-logo-${tamano} ${className}`} role="img" aria-label="NexoFaena SGI">
    <MarcaNexoFaena />
    <div className="nx-logo-texto">
      <span className="nx-logo-nombre">
        <strong>Nexo</strong>Faena
      </span>
      {conBajada && <span className="nx-logo-bajada">{bajada}</span>}
    </div>
  </div>
);

export default LogoNexoFaena;
