import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { FaChevronDown, FaSearch, FaTimes } from 'react-icons/fa';
import './SelectorBuscable.css';

// "Guantes Nitrilo" y "guantes nitrilo" son lo mismo para quien busca.
const normalizar = (texto) =>
  String(texto ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

/**
 * Un <select> en el que se puede escribir para filtrar.
 *
 * Al abrirlo aparece un campo con lupa: primero se listan las opciones cuyo
 * nombre empieza con lo escrito, y después las que lo contienen en otra parte
 * (o en el código). Se maneja con el mouse o con el teclado
 * (flechas, Enter y Esc).
 *
 * opciones: [{ valor, etiqueta, detalle?, busqueda? }]
 *   - etiqueta: texto principal (se usa para "empieza con")
 *   - detalle: texto secundario a la derecha (ej. stock)
 *   - busqueda: texto extra donde también buscar (ej. código)
 */
const SelectorBuscable = ({
  opciones,
  valor,
  onCambio,
  placeholder = '-- Seleccione --',
  placeholderBusqueda = 'Escribe para buscar…',
  deshabilitado = false,
  requerido = false,
  sinResultados = 'No hay coincidencias.',
}) => {
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState('');
  const [resaltado, setResaltado] = useState(0);
  const contenedorRef = useRef(null);
  const busquedaRef = useRef(null);
  const listaRef = useRef(null);
  const idLista = useId();

  const seleccionada = opciones.find((o) => String(o.valor) === String(valor));

  const filtradas = useMemo(() => {
    const consulta = normalizar(texto);
    if (!consulta) return opciones;

    const empiezan = [];
    const contienen = [];
    opciones.forEach((o) => {
      const etiqueta = normalizar(o.etiqueta);
      if (etiqueta.startsWith(consulta)) empiezan.push(o);
      else if (etiqueta.includes(consulta) || normalizar(o.busqueda).includes(consulta)) contienen.push(o);
    });
    return [...empiezan, ...contienen];
  }, [opciones, texto]);

  useEffect(() => {
    if (!abierto) return undefined;
    const alClickFuera = (e) => {
      if (contenedorRef.current && !contenedorRef.current.contains(e.target)) setAbierto(false);
    };
    document.addEventListener('mousedown', alClickFuera);
    return () => document.removeEventListener('mousedown', alClickFuera);
  }, [abierto]);

  useEffect(() => {
    if (abierto) busquedaRef.current?.focus();
  }, [abierto]);

  useEffect(() => { setResaltado(0); }, [texto]);

  useEffect(() => {
    listaRef.current?.children[resaltado]?.scrollIntoView({ block: 'nearest' });
  }, [resaltado]);

  const abrir = () => {
    if (deshabilitado) return;
    setTexto('');
    const indice = opciones.findIndex((o) => String(o.valor) === String(valor));
    setResaltado(Math.max(0, indice));
    setAbierto(true);
  };

  const elegir = (opcion) => {
    onCambio(opcion.valor);
    setAbierto(false);
  };

  const alTeclear = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setResaltado((i) => Math.min(i + 1, filtradas.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setResaltado((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault(); // no enviar el formulario
      if (filtradas[resaltado]) elegir(filtradas[resaltado]);
    } else if (e.key === 'Escape' || e.key === 'Tab') {
      setAbierto(false);
    }
  };

  return (
    <div className={`sb ${abierto ? 'sb-abierto' : ''}`} ref={contenedorRef}>
      {/* Campo oculto para que "required" del formulario siga funcionando. */}
      {requerido && (
        <input
          className="sb-requerido"
          tabIndex={-1}
          aria-hidden="true"
          required
          value={seleccionada ? String(valor) : ''}
          onChange={() => {}}
          onFocus={abrir}
        />
      )}

      {!abierto ? (
        <button
          type="button"
          className="sb-boton"
          onClick={abrir}
          disabled={deshabilitado}
          aria-haspopup="listbox"
          aria-expanded="false"
        >
          <FaSearch className="sb-lupa" />
          <span className={seleccionada ? 'sb-valor' : 'sb-placeholder'}>
            {seleccionada ? seleccionada.etiqueta : placeholder}
          </span>
          {seleccionada?.detalle && <span className="sb-detalle">{seleccionada.detalle}</span>}
          <FaChevronDown className="sb-flecha" />
        </button>
      ) : (
        <div className="sb-busqueda">
          <FaSearch className="sb-lupa" />
          <input
            ref={busquedaRef}
            type="text"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={alTeclear}
            placeholder={placeholderBusqueda}
            role="combobox"
            aria-expanded="true"
            aria-controls={idLista}
            aria-autocomplete="list"
            autoComplete="off"
          />
          {texto && (
            <button type="button" className="sb-limpiar" onClick={() => { setTexto(''); busquedaRef.current?.focus(); }} aria-label="Borrar búsqueda">
              <FaTimes />
            </button>
          )}
        </div>
      )}

      {abierto && (
        <ul className="sb-lista" role="listbox" id={idLista} ref={listaRef}>
          {filtradas.length === 0 ? (
            <li className="sb-vacio">{sinResultados}</li>
          ) : (
            filtradas.map((o, i) => (
              <li
                key={o.valor}
                role="option"
                aria-selected={String(o.valor) === String(valor)}
                className={`sb-opcion ${i === resaltado ? 'sb-resaltada' : ''} ${String(o.valor) === String(valor) ? 'sb-elegida' : ''}`}
                onMouseEnter={() => setResaltado(i)}
                onMouseDown={(e) => { e.preventDefault(); elegir(o); }}
              >
                <span className="sb-opcion-etiqueta">{o.etiqueta}</span>
                {o.detalle && <span className="sb-detalle">{o.detalle}</span>}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
};

export default SelectorBuscable;
