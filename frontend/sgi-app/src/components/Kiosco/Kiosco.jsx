import { useState, useEffect, useRef, useCallback } from 'react';
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
} from 'react-icons/fa';

import api from '../../api';
import { db } from '../../db';
import { useGeolocalizacion } from '../../hooks/useGeolocalizacion';
import { sincronizarEntregasPendientes } from '../../services/entregasOffline';
import './Kiosco.css';

// face_recognition_model entrega vectores de 128 floats. 0.6 es el default
// que usa la propia clase FaceMatcher de face-api.js (0.5 resultó
// demasiado estricto en la práctica).
const UMBRAL_DISTANCIA_FACIAL = 0.6;
const LECTURAS_CONSECUTIVAS_REQUERIDAS = 2;
const INTERVALO_DETECCION_MS = 300;
// Medido en vivo con webgl: ~47ms por lectura — con ese margen, muestrear
// mucho más rápido durante la verificación (girar la cabeza dura ~500ms-1s,
// mucho más margen que un parpadeo, pero igual conviene ir rápido).
const INTERVALO_VERIFICACION_MS = 90;
const OPCIONES_DETECTOR_FACIAL = new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.4 });

// --- Verificación de vida: giro de cabeza (anti-suplantación) ---
// Una foto sostenida frente a la cámara no puede girar sobre su propio eje
// cuando se le pide — a diferencia del parpadeo (muy rápido, difícil de
// muestrear a tiempo con una webcam común), un giro de cabeza es un
// movimiento grande y lento, mucho más fácil de capturar de forma fiable.
//
// "Yaw" (ángulo horizontal) estimado sin librería de pose 3D: se mide cuánto
// se desplaza la punta de la nariz respecto al centro de los ojos,
// normalizado por la distancia entre ojos (así no importa qué tan cerca o
// lejos esté la persona de la cámara). De frente, la nariz queda centrada
// (~0); al girar la cabeza hacia un lado, se desplaza notoriamente.
const UMBRAL_GIRO_CABEZA = 0.14;
const TIMEOUT_VERIFICACION_MS = 10000;
// Recién en el 2do fallo consecutivo se manda la alerta: un solo timeout
// puede ser alguien que no giró a tiempo, no necesariamente un intento real
// de suplantación.
const INTENTOS_FALLIDOS_PARA_ALERTAR = 2;

const centroPuntos = (puntos) => {
  const s = puntos.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
  return { x: s.x / puntos.length, y: s.y / puntos.length };
};

const calcularYaw = (landmarks) => {
  const ojoIzq = centroPuntos(landmarks.getLeftEye());
  const ojoDer = centroPuntos(landmarks.getRightEye());
  const nariz = landmarks.getNose()[3]; // punta de la nariz (landmark 30)
  const centroOjos = { x: (ojoIzq.x + ojoDer.x) / 2, y: (ojoIzq.y + ojoDer.y) / 2 };
  const anchoOjos = Math.hypot(ojoDer.x - ojoIzq.x, ojoDer.y - ojoIzq.y);
  return anchoOjos > 0 ? (nariz.x - centroOjos.x) / anchoOjos : 0;
};

const Kiosco = () => {
  const [fase, setFase] = useState('cargando-modelos');
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');

  const [bodegaId, setBodegaId] = useState(localStorage.getItem('kiosco_bodega_id') || '');
  const [bodegas, setBodegas] = useState([]);

  const [trabajadores, setTrabajadores] = useState([]);
  const [inventario, setInventario] = useState([]);
  const [trabajadorActual, setTrabajadorActual] = useState(null);
  const [pendientesDevolucion, setPendientesDevolucion] = useState([]);
  const [estadosDevolucion, setEstadosDevolucion] = useState({});

  const [rutManual, setRutManual] = useState('');
  const [carrito, setCarrito] = useState({});
  const [unidadesDisponibles, setUnidadesDisponibles] = useState([]);
  const [unidadesSeleccionadas, setUnidadesSeleccionadas] = useState({});

  const [modelosListos, setModelosListos] = useState(false);
  const [camaraActiva, setCamaraActiva] = useState(false);
  const [verificandoVida, setVerificandoVida] = useState(false);
  const [modoVerificacion, setModoVerificacion] = useState('reconocer');
  const [debugFacial, setDebugFacial] = useState({ distancia: null, giro: null, backend: null, msPorLectura: null });

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const intervaloDeteccionRef = useRef(null);
  const procesandoDeteccionRef = useRef(false);
  const candidatoRef = useRef({ id: null, veces: 0 });
  const verificacionRef = useRef(null);
  const intentosFallidosRef = useRef({});
  const trabajadoresRef = useRef([]);
  const sigCanvas = useRef({});

  const { capturar: capturarGeolocalizacion } = useGeolocalizacion();

  useEffect(() => {
    trabajadoresRef.current = trabajadores;
  }, [trabajadores]);

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

    return () => detenerCamara();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cargarDatos = async () => {
    try {
      if (!navigator.onLine) throw new Error('OFFLINE');

      const [resTrab, resInv, resBodegas, resUnidades] = await Promise.all([
        api.get('/trabajadores/?activo=true'),
        api.get('/inventario/'),
        api.get('/bodegas/'),
        api.get('/unidades-activo/?estado=DISPONIBLE').catch(() => ({ data: [] })),
      ]);

      setTrabajadores(resTrab.data);
      setInventario(resInv.data);
      setBodegas(resBodegas.data);
      // Las unidades (radios, etc.) no se cachean offline a propósito: igual
      // que en Entregas.jsx, asignar un equipo devolutivo exige conexión
      // para no arriesgarse a entregar el mismo radio a dos personas.
      setUnidadesDisponibles(resUnidades.data);

      await db.cache_trabajadores.bulkPut(resTrab.data);
      await db.cache_inventario.bulkPut(resInv.data);
      await db.cache_bodegas.bulkPut(resBodegas.data);

      return resBodegas.data;
    } catch {
      const [localTrab, localInv, localBodegas] = await Promise.all([
        db.cache_trabajadores.toArray(),
        db.cache_inventario.toArray(),
        db.cache_bodegas.toArray(),
      ]);

      setTrabajadores(localTrab);
      setInventario(localInv);
      setBodegas(localBodegas);

      return localBodegas;
    }
  };

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

  // --- Cámara + reconocimiento continuo ---

  useEffect(() => {
    if (fase === 'reconociendo') {
      iniciarCamara();
    } else {
      detenerCamara();
    }

    return () => detenerCamara();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fase]);

  const iniciarCamara = async () => {
    if (streamRef.current) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;

      candidatoRef.current = { id: null, veces: 0 };
      verificacionRef.current = null;
      procesandoDeteccionRef.current = false;
      setVerificandoVida(false);
      setCamaraActiva(true);
      setError('');

      const backend = faceapi.tf?.getBackend?.() || 'desconocido';
      setDebugFacial((prev) => ({ ...prev, backend }));

      intervaloDeteccionRef.current = setInterval(tickDeteccion, INTERVALO_DETECCION_MS);
    } catch (err) {
      console.error(err);
      setError(
        'No se pudo acceder a la cámara. Revisa el permiso del navegador. ' +
        'Si el kiosco se abre por IP de red (no localhost/https), el navegador puede bloquear la cámara por ser un origen no seguro.'
      );
    }
  };

  const detenerCamara = () => {
    if (intervaloDeteccionRef.current) clearInterval(intervaloDeteccionRef.current);
    intervaloDeteccionRef.current = null;
    procesandoDeteccionRef.current = false;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    setCamaraActiva(false);
    setDebugFacial({ distancia: null, giro: null, backend: null, msPorLectura: null });
  };

  const reprogramarIntervalo = (ms) => {
    if (intervaloDeteccionRef.current) clearInterval(intervaloDeteccionRef.current);
    intervaloDeteccionRef.current = setInterval(tickDeteccion, ms);
  };

  const tickDeteccion = async () => {
    if (procesandoDeteccionRef.current) return;
    procesandoDeteccionRef.current = true;
    const inicio = performance.now();

    try {
      await detectarRostro();
    } finally {
      setDebugFacial((prev) => ({ ...prev, msPorLectura: Math.round(performance.now() - inicio) }));
      procesandoDeteccionRef.current = false;
    }
  };

  const detectarRostro = useCallback(async () => {
    if (!videoRef.current || videoRef.current.readyState < 2) return;

    if (verificacionRef.current) {
      const deteccion = await faceapi.detectSingleFace(videoRef.current, OPCIONES_DETECTOR_FACIAL).withFaceLandmarks();
      procesarTickVerificacion(deteccion);
      return;
    }

    const deteccion = await faceapi
      .detectSingleFace(videoRef.current, OPCIONES_DETECTOR_FACIAL)
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (!deteccion) {
      candidatoRef.current = { id: null, veces: 0 };
      setDebugFacial((prev) => ({ ...prev, distancia: null }));
      return;
    }

    let mejorId = null;
    let mejorDistancia = Infinity;

    for (const t of trabajadoresRef.current) {
      if (!t.face_descriptor || t.face_descriptor.length !== 128) continue;

      const distancia = faceapi.euclideanDistance(deteccion.descriptor, t.face_descriptor);
      if (distancia < mejorDistancia) {
        mejorDistancia = distancia;
        mejorId = t.id;
      }
    }

    setDebugFacial((prev) => ({ ...prev, distancia: mejorId === null ? null : mejorDistancia.toFixed(3) }));

    if (mejorId === null || mejorDistancia > UMBRAL_DISTANCIA_FACIAL) {
      candidatoRef.current = { id: null, veces: 0 };
      return;
    }

    if (candidatoRef.current.id === mejorId) {
      candidatoRef.current.veces += 1;
    } else {
      candidatoRef.current = { id: mejorId, veces: 1 };
    }

    if (candidatoRef.current.veces >= LECTURAS_CONSECUTIVAS_REQUERIDAS) {
      const trabajador = trabajadoresRef.current.find((t) => t.id === mejorId);
      if (trabajador) {
        candidatoRef.current = { id: null, veces: 0 };
        verificacionRef.current = { trabajador, inicio: Date.now(), yawBase: null, modo: 'reconocer' };
        reprogramarIntervalo(INTERVALO_VERIFICACION_MS);
        setModoVerificacion('reconocer');
        setVerificandoVida(true);
        setError('');
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trabajadores]);

  const procesarTickVerificacion = (deteccion) => {
    const verificacion = verificacionRef.current;
    if (!verificacion) return;

    if (Date.now() - verificacion.inicio > TIMEOUT_VERIFICACION_MS) {
      manejarFalloVerificacion(verificacion.trabajador);
      return;
    }

    if (!deteccion) return;

    const yaw = calcularYaw(deteccion.landmarks);
    setDebugFacial((prev) => ({ ...prev, giro: yaw.toFixed(3) }));

    if (verificacion.yawBase === null) {
      verificacion.yawBase = yaw;
      return;
    }

    const desviacion = Math.abs(yaw - verificacion.yawBase);

    if (desviacion > UMBRAL_GIRO_CABEZA) {
      const trabajador = verificacion.trabajador;
      const modo = verificacion.modo;
      intentosFallidosRef.current[trabajador.id] = 0;
      verificacionRef.current = null;
      reprogramarIntervalo(INTERVALO_DETECCION_MS);
      setVerificandoVida(false);

      if (modo === 'enrolar') {
        finalizarEnrolamiento(trabajador);
      } else {
        confirmarTrabajador(trabajador);
      }
    }
  };

  const manejarFalloVerificacion = async (trabajador) => {
    verificacionRef.current = null;
    reprogramarIntervalo(INTERVALO_DETECCION_MS);
    setVerificandoVida(false);
    candidatoRef.current = { id: null, veces: 0 };

    const fallosPrevios = intentosFallidosRef.current[trabajador.id] || 0;
    const fallosActuales = fallosPrevios + 1;

    if (fallosActuales >= INTENTOS_FALLIDOS_PARA_ALERTAR) {
      intentosFallidosRef.current[trabajador.id] = 0;
      setError(`⚠️ No se pudo confirmar que ${trabajador.nombres} esté presente en persona. Se avisó a supervisión.`);

      try {
        await api.post(`/trabajadores/${trabajador.id}/reportar-suplantacion/`, { bodega: bodegaId || null });
      } catch (err) {
        console.error('No se pudo registrar la alerta de suplantación:', err);
      }
    } else {
      setError('⚠️ No detectamos el giro a tiempo. Mira a la cámara e inténtalo de nuevo.');
      intentosFallidosRef.current[trabajador.id] = fallosActuales;
    }
  };

  // --- Confirmado: arma el menú (retirar / devolver) ---

  const confirmarTrabajador = async (trabajador) => {
    detenerCamara();
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

  // --- Enrolamiento manual por RUT (primera vez / cámara no reconoce) ---

  const buscarPorRutYEnrolar = () => {
    setError('');
    const texto = rutManual.toLowerCase().trim();
    const trabajador = trabajadores.find((t) => t.rut?.toLowerCase().includes(texto));

    if (!texto) {
      setError('Escribe tu RUT en el campo de arriba.');
      return;
    }

    if (!trabajador) {
      setError('No encontramos ese RUT en el sistema. Contacta a Administración para registrarte primero.');
      return;
    }

    if (!videoRef.current || videoRef.current.readyState < 2) {
      setError('La cámara no está lista. Espera un segundo e intenta de nuevo.');
      return;
    }

    // No captura el rostro de inmediato: exige el mismo giro de cabeza que
    // el reconocimiento normal antes de guardar nada. Sin esto, cualquiera
    // podría enrolar una foto sostenida frente a la cámara bajo el RUT de
    // otra persona — el punto débil que quedaba abierto.
    candidatoRef.current = { id: null, veces: 0 };
    verificacionRef.current = { trabajador, inicio: Date.now(), yawBase: null, modo: 'enrolar' };
    reprogramarIntervalo(INTERVALO_VERIFICACION_MS);
    setModoVerificacion('enrolar');
    setVerificandoVida(true);
  };

  const finalizarEnrolamiento = async (trabajador) => {
    if (!videoRef.current || videoRef.current.readyState < 2) {
      setError('Se perdió la cámara justo al confirmar. Intenta de nuevo.');
      return;
    }

    // El descriptor se captura recién ahora (no el de la primera lectura):
    // así lo que se guarda es el rostro que efectivamente superó el chequeo
    // de vida, en el mismo instante.
    const deteccion = await faceapi
      .detectSingleFace(videoRef.current, OPCIONES_DETECTOR_FACIAL)
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (!deteccion) {
      setError('No detectamos tu rostro justo al confirmar. Intenta de nuevo.');
      return;
    }

    try {
      const descriptor = Array.from(deteccion.descriptor);
      await api.post(`/trabajadores/${trabajador.id}/enrolar-rostro/`, { face_descriptor: descriptor });

      confirmarTrabajador({ ...trabajador, face_descriptor: descriptor });
    } catch (err) {
      console.error(err);
      setError('No se pudo registrar tu rostro (requiere conexión la primera vez). Intenta de nuevo cuando haya internet.');
    }
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

  if (fase === 'cargando-modelos') {
    return (
      <div className="kiosco-wrapper kiosco-centrado">
        <div className="kiosco-spinner" />
        <p>Cargando reconocimiento facial…</p>
        {error && <div className="kiosco-error">{error}</div>}
      </div>
    );
  }

  if (fase === 'configurar-bodega') {
    return (
      <div className="kiosco-wrapper kiosco-centrado">
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
            <SignatureCanvas ref={sigCanvas} penColor="#001529" canvasProps={{ className: 'kiosco-firma-canvas' }} />
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
