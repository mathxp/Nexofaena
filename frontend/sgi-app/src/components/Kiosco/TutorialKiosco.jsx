import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FaUser,
  FaArrowLeft,
  FaArrowRight,
  FaIdCard,
  FaHardHat,
  FaGlasses,
  FaHandPaper,
  FaPenFancy,
  FaTimes,
  FaChevronLeft,
  FaChevronRight,
  FaLightbulb,
} from 'react-icons/fa';

import './TutorialKiosco.css';

// El kiosco queda sin nadie mirando: si alguien abre la guía y se va, se
// cierra sola para que la cámara vuelva a quedar lista para el siguiente.
const MS_INACTIVIDAD = 60_000;
const UMBRAL_DESLIZAR_PX = 50;

const IlustracionCamara = () => (
  <div className="tk-ilus tk-ilus-camara">
    <div className="tk-marco">
      <span className="tk-esquina tk-esquina-1" />
      <span className="tk-esquina tk-esquina-2" />
      <span className="tk-esquina tk-esquina-3" />
      <span className="tk-esquina tk-esquina-4" />
      <FaUser className="tk-rostro" />
      <span className="tk-linea-escaneo" />
    </div>
  </div>
);

const IlustracionGiro = () => (
  <div className="tk-ilus tk-ilus-giro">
    <FaArrowLeft className="tk-flecha tk-flecha-izq" />
    <div className="tk-circulo">
      <FaUser className="tk-rostro tk-rostro-girando" />
    </div>
    <FaArrowRight className="tk-flecha tk-flecha-der" />
  </div>
);

const IlustracionRut = () => (
  <div className="tk-ilus tk-ilus-rut">
    <div className="tk-mock-input">
      <FaIdCard />
      <span className="tk-mock-texto">12.345.678-9</span>
      <span className="tk-cursor" />
    </div>
    <div className="tk-mock-boton">Registrar rostro</div>
  </div>
);

const IlustracionEpp = () => (
  <div className="tk-ilus tk-ilus-epp">
    <div className="tk-mock-producto tk-seleccionado">
      <FaHardHat />
      <span>Casco</span>
      <div className="tk-mock-cantidad"><b>−</b> 1 <b>+</b></div>
    </div>
    <div className="tk-mock-producto">
      <FaGlasses />
      <span>Lentes</span>
    </div>
    <div className="tk-mock-producto tk-seleccionado">
      <FaHandPaper />
      <span>Guantes</span>
      <div className="tk-mock-cantidad"><b>−</b> 2 <b>+</b></div>
    </div>
  </div>
);

const IlustracionFirma = () => (
  <div className="tk-ilus tk-ilus-firma">
    <div className="tk-mock-firma">
      <svg viewBox="0 0 220 80" aria-hidden="true">
        <path
          className="tk-trazo"
          d="M12 58c18-30 30-40 38-30s-14 34-4 34 22-44 34-40-8 36 4 34 18-26 28-22 4 20 14 18 18-16 30-14 18 8 30 6"
        />
      </svg>
      <FaPenFancy className="tk-lapiz" />
    </div>
    <div className="tk-mock-boton">Confirmar y salir</div>
  </div>
);

const PASOS = [
  {
    titulo: 'Ponte frente a la cámara',
    texto: 'Mírala de frente y quédate quieto un momento. El kiosco te reconoce solo, sin tocar nada.',
    consejos: ['A unos 50 cm de la pantalla', 'Sácate lentes oscuros o mascarilla', 'Que haya buena luz en tu cara'],
    Ilustracion: IlustracionCamara,
  },
  {
    titulo: 'Gira la cabeza hacia un lado',
    texto: 'Cuando aparezca el aviso, gira la cabeza suavemente. Así el sistema sabe que eres tú en persona y no una foto.',
    consejos: ['Un giro lento basta', 'No hace falta acercarse más'],
    Ilustracion: IlustracionGiro,
  },
  {
    titulo: '¿Primera vez? Registra tu rostro',
    texto: 'Si el kiosco no te reconoce, escribe tu RUT en el recuadro de abajo y toca "Registrar rostro". Se hace una sola vez.',
    consejos: ['Con o sin puntos y guion', 'Si tu RUT no aparece, avisa al bodeguero'],
    Ilustracion: IlustracionRut,
  },
  {
    titulo: 'Elige lo que vas a retirar',
    texto: 'Toca "Retirar EPP" y marca los productos que necesitas. Ajusta la cantidad con los botones − y +.',
    consejos: ['Si debes un radio o equipo, devuélvelo primero', 'Revisa la cantidad antes de seguir'],
    Ilustracion: IlustracionEpp,
  },
  {
    titulo: 'Firma y confirma',
    texto: 'Firma con el dedo en el recuadro y toca "Confirmar y salir". El retiro queda registrado a tu nombre.',
    consejos: ['Sin internet también funciona: tu retiro se guarda y se envía solo'],
    Ilustracion: IlustracionFirma,
  },
];

const TutorialKiosco = ({ onCerrar }) => {
  const [paso, setPaso] = useState(0);
  const inicioToque = useRef(null);
  const temporizador = useRef(null);

  const esUltimo = paso === PASOS.length - 1;
  const { titulo, texto, consejos, Ilustracion } = PASOS[paso];

  const reiniciarInactividad = useCallback(() => {
    clearTimeout(temporizador.current);
    temporizador.current = setTimeout(onCerrar, MS_INACTIVIDAD);
  }, [onCerrar]);

  const irA = useCallback((nuevo) => {
    setPaso(Math.max(0, Math.min(PASOS.length - 1, nuevo)));
    reiniciarInactividad();
  }, [reiniciarInactividad]);

  useEffect(() => {
    reiniciarInactividad();
    return () => clearTimeout(temporizador.current);
  }, [reiniciarInactividad]);

  useEffect(() => {
    const alPresionar = (e) => {
      if (e.key === 'Escape') onCerrar();
      if (e.key === 'ArrowRight') irA(paso + 1);
      if (e.key === 'ArrowLeft') irA(paso - 1);
    };
    window.addEventListener('keydown', alPresionar);
    return () => window.removeEventListener('keydown', alPresionar);
  }, [paso, irA, onCerrar]);

  const alTocar = (e) => {
    inicioToque.current = e.clientX;
  };

  const alSoltar = (e) => {
    if (inicioToque.current === null) return;
    const delta = e.clientX - inicioToque.current;
    inicioToque.current = null;
    if (Math.abs(delta) < UMBRAL_DESLIZAR_PX) return;
    irA(delta < 0 ? paso + 1 : paso - 1);
  };

  return (
    <div className="tk-fondo" role="dialog" aria-modal="true" aria-labelledby="tk-titulo">
      <div className="tk-tarjeta" onPointerDown={alTocar} onPointerUp={alSoltar}>
        <div className="tk-cabecera">
          <span className="tk-contador">Paso {paso + 1} de {PASOS.length}</span>
          <button type="button" className="tk-cerrar" onClick={onCerrar} aria-label="Cerrar la guía">
            <FaTimes />
          </button>
        </div>

        <div className="tk-progreso">
          <div className="tk-progreso-barra" style={{ width: `${((paso + 1) / PASOS.length) * 100}%` }} />
        </div>

        {/* key={paso}: remonta el contenido para que la animación de entrada
            y la de la ilustración vuelvan a correr en cada paso. */}
        <div className="tk-contenido" key={paso}>
          <Ilustracion />

          <h2 id="tk-titulo" className="tk-titulo">{titulo}</h2>
          <p className="tk-texto">{texto}</p>

          <ul className="tk-consejos">
            {consejos.map((c) => (
              <li key={c}><FaLightbulb /> {c}</li>
            ))}
          </ul>
        </div>

        <div className="tk-puntos" role="tablist" aria-label="Pasos de la guía">
          {PASOS.map((p, i) => (
            <button
              key={p.titulo}
              type="button"
              role="tab"
              aria-selected={i === paso}
              aria-label={`Ir al paso ${i + 1}: ${p.titulo}`}
              className={`tk-punto ${i === paso ? 'activo' : ''}`}
              onClick={() => irA(i)}
            />
          ))}
        </div>

        <div className="tk-acciones">
          <button
            type="button"
            className="tk-btn tk-btn-secundario"
            onClick={() => irA(paso - 1)}
            disabled={paso === 0}
          >
            <FaChevronLeft /> Anterior
          </button>

          {esUltimo ? (
            <button type="button" className="tk-btn tk-btn-primario" onClick={onCerrar}>
              Entendido, empezar
            </button>
          ) : (
            <button type="button" className="tk-btn tk-btn-primario" onClick={() => irA(paso + 1)}>
              Siguiente <FaChevronRight />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default TutorialKiosco;
