import { useState, useEffect, useRef } from 'react';
import * as faceapi from 'face-api.js';
import SignatureCanvas from 'react-signature-canvas';
import {
  FaCamera,
  FaIdCard,
  FaCheckCircle,
  FaShoppingBasket,
  FaPenFancy,
  FaSignOutAlt,
  FaBroadcastTower,
  FaTools,
  FaUndo,
  FaWifi,
  FaSignal,
} from 'react-icons/fa';

import api from '../../api';
import { db } from '../../db';
import { useGeolocalizacion } from '../../hooks/useGeolocalizacion';
import { sincronizarEntregasPendientes } from '../../services/entregasOffline';
import { useWakeLock } from './hooks/useWakeLock';
import { useConexionKiosco } from './hooks/useConexionKiosco';
import { useDatosKioscoCache } from './hooks/useDatosKioscoCache';
import { useReconocimientoFacial } from './hooks/useReconocimientoFacial';
import './Kiosco.css';

const Kiosco = () => {
  const [fase, setFase] = useState('cargando-modelos');
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');

  const [bodegaId, setBodegaId] = useState(localStorage.getItem('kiosco_bodega_id') || '');
  const [modelosListos, setModelosListos] = useState(false);

  const [trabajadorActual, setTrabajadorActual] = useState(null);
  const [pendientesDevolucion, setPendientesDevolucion] = useState([]);
  const [estadosDevolucion, setEstadosDevolucion] = useState({});

  const [carrito, setCarrito] = useState({});
  const [unidadesSeleccionadas, setUnidadesSeleccionadas] = useState({});

  const sigCanvas = useRef({});

  const { capturar: capturarGeolocalizacion } = useGeolocalizacion();
  const isOffline = useConexionKiosco();
  useWakeLock();

  const { trabajadores, inventario, bodegas, unidadesDisponibles, cargarDatos } = useDatosKioscoCache();

  // --- Confirmado: arma el menú (retirar / devolver) ---
  // Es el callback que useReconocimientoFacial() invoca tanto cuando
  // reconoce una cara conocida como cuando termina de enrolar una nueva
  // (ahí llega con face_descriptor recién asignado) — el hook ya se
  // encargó de apagar la cámara antes de llamar esto.
  const confirmarTrabajador = async (trabajador) => {
    setTrabajadorActual(trabajador);
    setCarrito({});
    setUnidadesSeleccionadas({});
    setEstadosDevolucion({});
    setError('');
    setMensaje(`✅ Bienvenido, ${trabajador.nombres}`);

    try {
      const res = await api.get(`/detalles-entrega-epp/?trabajador=${trabajador.id}&pendientes=true`);
      setPendientesDevolucion(res.data);
    } catch (err) {
      console.error(err);
      setPendientesDevolucion([]);
    }

    setFase('menu');
  };

  const {
    videoRef,
    camaraActiva,
    verificandoVida,
    modoVerificacion,
    debugFacial,
    rutManual,
    setRutManual,
    buscarPorRutYEnrolar,
    UMBRAL_DISTANCIA_FACIAL,
    UMBRAL_GIRO_CABEZA,
  } = useReconocimientoFacial({
    activo: fase === 'reconociendo',
    trabajadores,
    bodegaId,
    onReconocido: confirmarTrabajador,
    setError,
  });

  // --- Carga inicial: modelos de face-api.js + caché de datos ---

  useEffect(() => {
    (async () => {
      try {
        await Promise.all([
          faceapi.nets.tinyFaceDetector.loadFromUri('/models'),
          faceapi.nets.faceLandmark68Net.loadFromUri('/models'),
          faceapi.nets.faceRecognitionNet.loadFromUri('/models'),
        ]);
      } catch (err) {
        console.error(err);
        setError('No se pudieron cargar los modelos de reconocimiento facial. Revisa la conexión e intenta de nuevo.');
        return;
      }

      const bodegasCargadas = await cargarDatos();
      setModelosListos(true);

      const bodegaGuardada = localStorage.getItem('kiosco_bodega_id');
      // Si la bodega guardada ya no existe (se borró, o el dato del
      // dispositivo quedó corrupto/de otra instalación), no hay forma de
      // volver a elegir una — antes esto dejaba el kiosco trabado en
      // "reconociendo" sin ningún control para cambiarla. Se valida contra
      // la lista real antes de confiar en el valor guardado.
      const bodegaValida = bodegaGuardada && bodegasCargadas.some((b) => String(b.id) === bodegaGuardada);

      if (bodegaGuardada && !bodegaValida) {
        localStorage.removeItem('kiosco_bodega_id');
      }

      setFase(bodegaValida ? 'reconociendo' : 'configurar-bodega');
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const guardarBodegaKiosco = (id) => {
    localStorage.setItem('kiosco_bodega_id', id);
    setBodegaId(id);
    setFase('reconociendo');
  };

  const cambiarBodega = () => {
    localStorage.removeItem('kiosco_bodega_id');
    setBodegaId('');
    setFase('configurar-bodega');
  };

  // --- Devolución de equipos devolutivos (radios, etc.) ---

  const marcarDevuelto = async (detalle) => {
    if (!navigator.onLine) {
      setError('⚠️ Se necesita conexión para registrar la devolución (evita asignar el mismo equipo dos veces).');
      return;
    }

    setError('');
    const estado = estadosDevolucion[detalle.id] || 'OPERATIVA';

    try {
      await api.post(`/detalles-entrega-epp/${detalle.id}/devolver/`, { estado_devolucion: estado });

      const etiqueta = detalle.unidad_activo_codigo || detalle.producto_nombre;
      setMensaje(`✅ ${etiqueta} devuelto correctamente${estado === 'DAÑADA' ? ' (marcado DAÑADA)' : ''}.`);
      setPendientesDevolucion((prev) => prev.filter((d) => d.id !== detalle.id));
      setTimeout(() => setMensaje(''), 3000);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Error al registrar la devolución.');
    }
  };

  // --- Autoservicio: selección de productos a retirar ---

  const productosDisponibles = inventario.filter(
    (item) =>
      String(item.bodega) === String(bodegaId) &&
      !item.es_devolutivo &&
      Number(item.stock_actual) > 0
  );

  const unidadesEnBodega = unidadesDisponibles.filter((u) => String(u.bodega) === String(bodegaId));

  // No puede retirar un radio/equipo nuevo mientras deba otro: si no
  // devuelve el que tiene, nadie sabría cuál de los dos le corresponde
  // devolver después, y el stock de devolutivos quedaría descuadrado.
  const puedeRetirarDevolutivo = pendientesDevolucion.length === 0;

  const toggleProducto = (id) => {
    setCarrito((prev) => {
      const nuevo = { ...prev };
      if (nuevo[id]) delete nuevo[id];
      else nuevo[id] = 1;
      return nuevo;
    });
  };

  const cambiarCantidad = (id, delta, max) => {
    setCarrito((prev) => {
      const actual = prev[id] || 0;
      const nuevo = Math.min(max, Math.max(1, actual + delta));
      return { ...prev, [id]: nuevo };
    });
  };

  const toggleUnidad = (unidad) => {
    if (!puedeRetirarDevolutivo) return;

    setUnidadesSeleccionadas((prev) => {
      const nuevo = { ...prev };
      if (nuevo[unidad.id]) {
        delete nuevo[unidad.id];
      } else {
        nuevo[unidad.id] = {
          inventario_id: unidad.inventario,
          codigo: unidad.codigo,
          producto_nombre: unidad.producto_nombre,
        };
      }
      return nuevo;
    });
  };

  const irAFirma = () => {
    setError('');

    const hayUnidades = Object.keys(unidadesSeleccionadas).length > 0;

    if (Object.keys(carrito).length === 0 && !hayUnidades) {
      setError('Selecciona al menos un producto para continuar.');
      return;
    }

    if (hayUnidades && !navigator.onLine) {
      setError('⚠️ Retirar un radio/equipo requiere conexión, para no asignarlo dos veces. Quita la selección o espera a tener internet.');
      return;
    }

    setFase('firma');
  };

  // --- Firma + envío del retiro ---

  const limpiarFirma = () => sigCanvas.current?.clear();

  const confirmarSalida = async () => {
    setError('');

    const hayUnidades = Object.keys(unidadesSeleccionadas).length > 0;

    if (sigCanvas.current.isEmpty()) {
      setError('Firma para confirmar el retiro.');
      return;
    }

    // Se revalida acá (no solo en irAFirma): la conexión pudo caerse
    // mientras firmaba. Un radio nunca puede quedar en la cola offline —
    // esa cola no sabe reservar una unidad específica, y dos kioscos
    // podrían asignar el mismo radio a dos personas distintas.
    if (hayUnidades && !navigator.onLine) {
      setError('⚠️ Se perdió la conexión. Los radios/equipos no se pueden retirar sin internet — vuelve a intentar cuando haya conexión.');
      setFase('autoservicio');
      return;
    }

    setFase('enviando');

    const firmaBase64 = sigCanvas.current.getCanvas().toDataURL('image/png');
    const geolocalizacion = await capturarGeolocalizacion();
    const usuarioKioscoId = Number(localStorage.getItem('user_id'));

    const detallesProductos = Object.keys(carrito).map((productoId) => ({
      inventario: parseInt(productoId),
      cantidad: carrito[productoId],
      talla: 'N/A',
    }));

    const detallesUnidades = Object.keys(unidadesSeleccionadas).map((unidadId) => ({
      inventario: unidadesSeleccionadas[unidadId].inventario_id,
      cantidad: 1,
      talla: 'N/A',
      unidad_activo: parseInt(unidadId),
    }));

    const detalles = [...detallesProductos, ...detallesUnidades];

    const payloadServidor = {
      trabajador: trabajadorActual.id,
      usuario: usuarioKioscoId,
      bodega: parseInt(bodegaId),
      firma_base64: firmaBase64,
      observacion: `Autoservicio kiosco — ${trabajadorActual.nombres} ${trabajadorActual.apellido_paterno} (RUT ${trabajadorActual.rut})`,
      estado: 'COMPLETADA',
      canal: 'KIOSCO',
      latitud: geolocalizacion?.latitud ?? null,
      longitud: geolocalizacion?.longitud ?? null,
      precision_metros: geolocalizacion?.precision_metros ?? null,
      geolocalizacion_capturada_en: geolocalizacion?.geolocalizacion_capturada_en ?? null,
      detalles,
    };

    const payloadLocal = {
      trabajador_id: trabajadorActual.id,
      usuario_id: usuarioKioscoId,
      bodega_id: parseInt(bodegaId),
      productos: carrito,
      firma_base64: firmaBase64,
      observacion: payloadServidor.observacion,
      fecha: new Date().toISOString(),
      latitud: payloadServidor.latitud,
      longitud: payloadServidor.longitud,
      precision_metros: payloadServidor.precision_metros,
      geolocalizacion_capturada_en: payloadServidor.geolocalizacion_capturada_en,
      canal: 'KIOSCO',
      sincronizado: 0,
    };

    try {
      if (navigator.onLine) {
        await api.post('/entregas-epp/', payloadServidor);

        if (hayUnidades) {
          const codigos = Object.values(unidadesSeleccionadas).map((u) => u.codigo).join(', ');
          setMensaje(`✅ Retiro registrado. Recuerda devolver ${codigos} antes de tu próximo turno.`);
        } else {
          setMensaje('✅ Retiro registrado correctamente.');
        }
      } else {
        await db.entregas_pendientes.add(payloadLocal);
        setMensaje('📡 Sin conexión: retiro guardado, se enviará solo.');
      }
    } catch (err) {
      console.error(err);
      await db.entregas_pendientes.add(payloadLocal);
      setMensaje('📡 Retiro guardado localmente, se enviará solo al recuperar conexión.');
    }

    setFase('confirmado');
    setTimeout(reiniciar, 4000);
  };

  const reiniciar = () => {
    sincronizarEntregasPendientes();
    setTrabajadorActual(null);
    setPendientesDevolucion([]);
    setCarrito({});
    setUnidadesSeleccionadas({});
    setRutManual('');
    setError('');
    setMensaje('');
    if (sigCanvas.current?.clear) sigCanvas.current.clear();
    setFase('reconociendo');
  };

  // --- Render ---

  const badgeConexion = (
    <div className={`kiosco-network-badge ${isOffline ? 'kiosco-badge-offline' : 'kiosco-badge-online'}`}>
      {isOffline ? (<><FaSignal /> Sin conexión</>) : (<><FaWifi /> Conectado</>)}
    </div>
  );

  if (fase === 'cargando-modelos') {
    return (
      <div className="kiosco-wrapper kiosco-centrado">
        {badgeConexion}
        <div className="kiosco-spinner" />
        <p>Cargando reconocimiento facial…</p>
        {error && <div className="kiosco-error">{error}</div>}
      </div>
    );
  }

  if (fase === 'configurar-bodega') {
    return (
      <div className="kiosco-wrapper kiosco-centrado">
        {badgeConexion}
        <h1 className="kiosco-titulo">Configuración del kiosco</h1>
        <p className="kiosco-subtitulo">Selecciona a qué bodega atiende este kiosco (se guarda en este dispositivo).</p>

        <select className="kiosco-select" value={bodegaId} onChange={(e) => setBodegaId(e.target.value)}>
          <option value="">-- Selecciona bodega --</option>
          {bodegas.map((b) => (
            <option key={b.id} value={b.id}>{b.nombre}</option>
          ))}
        </select>

        <button className="kiosco-btn-primario" disabled={!bodegaId} onClick={() => guardarBodegaKiosco(bodegaId)}>
          Guardar y continuar
        </button>
      </div>
    );
  }

  return (
    <div className="kiosco-wrapper">
      {badgeConexion}

      {(fase === 'reconociendo') && (
        <div className="kiosco-reconocimiento">
          <video ref={videoRef} autoPlay muted playsInline className="kiosco-video" />

          <button type="button" className="kiosco-btn-config" onClick={cambiarBodega} title="Cambiar la bodega de este kiosco">
            ⚙ Cambiar bodega
          </button>

          <div className="kiosco-overlay">
            {!verificandoVida ? (
              <>
                <FaCamera className="kiosco-icono-grande" />
                <h1>Acércate a la cámara</h1>
                <p>Te reconoceremos automáticamente para declarar tu retiro de pañol.</p>
              </>
            ) : (
              <>
                <FaCheckCircle className="kiosco-icono-grande kiosco-icono-exito" />
                <h1>Gira tu cabeza hacia un lado</h1>
                <p>
                  {modoVerificacion === 'enrolar'
                    ? 'Así confirmamos que el rostro que vamos a registrar es realmente tuyo.'
                    : 'Así confirmamos que estás presente en persona.'}
                </p>
              </>
            )}

            <div className="kiosco-enrolar-box">
              <p>¿Primera vez aquí?</p>
              <div className="kiosco-enrolar-input">
                <FaIdCard />
                <input
                  type="text"
                  placeholder="Ingresa tu RUT"
                  value={rutManual}
                  onChange={(e) => setRutManual(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && buscarPorRutYEnrolar()}
                />
                <button onClick={buscarPorRutYEnrolar}>Registrar rostro</button>
              </div>
            </div>

            {camaraActiva && (
              <div className="kiosco-debug-info">
                {!verificandoVida
                  ? `distancia: ${debugFacial.distancia ?? '—'} (umbral ${UMBRAL_DISTANCIA_FACIAL})`
                  : `giro: ${debugFacial.giro ?? '—'} (umbral ${UMBRAL_GIRO_CABEZA})`}
                {' · '}backend: {debugFacial.backend ?? '—'} · {debugFacial.msPorLectura ?? '—'}ms
              </div>
            )}

            {error && <div className="kiosco-error">{error}</div>}
          </div>
        </div>
      )}

      {fase === 'menu' && trabajadorActual && (
        <div className="kiosco-panel">
          <div className="kiosco-header-panel">
            <FaCheckCircle className="kiosco-icono-exito" />
            <div>
              <h2>{trabajadorActual.nombres} {trabajadorActual.apellido_paterno}</h2>
              <span>{trabajadorActual.cargo}</span>
            </div>
          </div>

          {mensaje && <div className="kiosco-mensaje-ok">{mensaje}</div>}
          {error && <div className="kiosco-error">{error}</div>}

          {pendientesDevolucion.length > 0 && (
            <div className="kiosco-devoluciones-box">
              <div className="kiosco-devoluciones-titulo">
                <FaBroadcastTower /> Tienes equipos por devolver
              </div>

              {pendientesDevolucion.map((detalle) => (
                <div key={detalle.id} className="kiosco-devolucion-item">
                  <span className="kiosco-devolucion-nombre">
                    {detalle.unidad_activo_codigo || detalle.producto_nombre}
                  </span>

                  <div className="kiosco-devolucion-acciones">
                    <div className="kiosco-estado-toggle">
                      <button
                        type="button"
                        className={(estadosDevolucion[detalle.id] || 'OPERATIVA') === 'OPERATIVA' ? 'activo' : ''}
                        onClick={() => setEstadosDevolucion((prev) => ({ ...prev, [detalle.id]: 'OPERATIVA' }))}
                      >
                        <FaCheckCircle /> Operativa
                      </button>
                      <button
                        type="button"
                        className={estadosDevolucion[detalle.id] === 'DAÑADA' ? 'activo danio' : 'danio'}
                        onClick={() => setEstadosDevolucion((prev) => ({ ...prev, [detalle.id]: 'DAÑADA' }))}
                      >
                        <FaTools /> Dañada
                      </button>
                    </div>

                    <button type="button" className="kiosco-btn-devolver" onClick={() => marcarDevuelto(detalle)}>
                      <FaUndo /> Devolver
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="kiosco-acciones kiosco-acciones-menu">
            <button className="kiosco-btn-secundario" onClick={reiniciar}>
              <FaSignOutAlt /> Listo, salir
            </button>
            <button className="kiosco-btn-primario" onClick={() => setFase('autoservicio')}>
              <FaShoppingBasket /> Retirar EPP
            </button>
          </div>
        </div>
      )}

      {fase === 'autoservicio' && trabajadorActual && (
        <div className="kiosco-panel">
          <div className="kiosco-header-panel">
            <FaShoppingBasket />
            <div>
              <h2>{trabajadorActual.nombres} {trabajadorActual.apellido_paterno}</h2>
              <span>¿Qué necesitas retirar?</span>
            </div>
          </div>

          {error && <div className="kiosco-error">{error}</div>}

          <div className="kiosco-scroll">
            <div className="kiosco-seccion">
              <div className="kiosco-seccion-titulo">EPP e insumos</div>

              <div className="kiosco-grid-productos">
                {productosDisponibles.length === 0 ? (
                  <div className="kiosco-vacio">No hay productos disponibles en esta bodega.</div>
                ) : (
                  productosDisponibles.map((p) => {
                    const seleccionado = !!carrito[p.id];
                    return (
                      <div key={p.id} className={`kiosco-producto ${seleccionado ? 'seleccionado' : ''}`}>
                        <div className="kiosco-producto-info" onClick={() => toggleProducto(p.id)}>
                          <span className="kiosco-producto-nombre">{p.nombre}</span>
                          <span className="kiosco-producto-stock">Stock: {p.stock_actual}</span>
                        </div>

                        {seleccionado && (
                          <div className="kiosco-cantidad">
                            <button onClick={() => cambiarCantidad(p.id, -1, p.stock_actual)}>−</button>
                            <span>{carrito[p.id]}</span>
                            <button onClick={() => cambiarCantidad(p.id, 1, p.stock_actual)}>+</button>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            <div className="kiosco-seccion">
              <div className="kiosco-seccion-titulo">
                <FaBroadcastTower /> Radios y equipos devolutivos
              </div>

              {!puedeRetirarDevolutivo ? (
                <div className="kiosco-devolutivos-bloqueado">
                  Ya tienes un equipo pendiente de devolver — devuélvelo antes de retirar otro (vuelve al menú anterior).
                </div>
              ) : unidadesEnBodega.length === 0 ? (
                <div className="kiosco-devolutivos-bloqueado">No hay equipos devolutivos disponibles en esta bodega.</div>
              ) : (
                <div className="kiosco-grid-unidades">
                  {unidadesEnBodega.map((unidad) => {
                    const seleccionada = !!unidadesSeleccionadas[unidad.id];
                    return (
                      <button
                        key={unidad.id}
                        type="button"
                        className={`kiosco-unidad ${seleccionada ? 'seleccionada' : ''}`}
                        onClick={() => toggleUnidad(unidad)}
                      >
                        <span className="kiosco-unidad-codigo">{unidad.codigo}</span>
                        <span className="kiosco-unidad-nombre">{unidad.producto_nombre}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="kiosco-acciones">
            <button className="kiosco-btn-secundario" onClick={() => setFase('menu')}>
              Volver
            </button>
            <button className="kiosco-btn-primario" onClick={irAFirma}>
              Continuar ({Object.keys(carrito).length + Object.keys(unidadesSeleccionadas).length})
            </button>
          </div>
        </div>
      )}

      {fase === 'firma' && (
        <div className="kiosco-panel">
          <div className="kiosco-header-panel">
            <FaPenFancy />
            <div>
              <h2>Firma para confirmar tu retiro</h2>
              <span>{trabajadorActual?.nombres} {trabajadorActual?.apellido_paterno}</span>
            </div>
          </div>

          {error && <div className="kiosco-error">{error}</div>}

          <div className="kiosco-firma-wrapper">
            <SignatureCanvas ref={sigCanvas} penColor="#0f2647" canvasProps={{ className: 'kiosco-firma-canvas' }} />
          </div>

          <button className="kiosco-btn-secundario" onClick={limpiarFirma}>Borrar firma</button>

          <div className="kiosco-acciones">
            <button className="kiosco-btn-secundario" onClick={() => setFase('autoservicio')}>Volver</button>
            <button className="kiosco-btn-primario" onClick={confirmarSalida}>Confirmar y salir</button>
          </div>
        </div>
      )}

      {fase === 'enviando' && (
        <div className="kiosco-centrado">
          <div className="kiosco-spinner" />
          <p>Registrando tu retiro…</p>
        </div>
      )}

      {fase === 'confirmado' && (
        <div className="kiosco-centrado">
          <FaCheckCircle className="kiosco-icono-grande kiosco-icono-exito" />
          <h1>¡Listo, {trabajadorActual?.nombres}!</h1>
          <p>{mensaje}</p>
        </div>
      )}
    </div>
  );
};

export default Kiosco;
