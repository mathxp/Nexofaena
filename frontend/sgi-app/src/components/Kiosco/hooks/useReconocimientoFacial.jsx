import { useCallback, useEffect, useRef, useState } from 'react';
import * as faceapi from 'face-api.js';

import api from '../../../api';

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
const RETRASO_REINTENTO_CAMARA_MS = 5000;

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

/**
 * Cámara + reconocimiento facial continuo + verificación de vida (giro de
 * cabeza) + enrolamiento manual por RUT. Reconocimiento y liveness viven en
 * un solo hook (no dos) porque comparten el mismo intervalo de muestreo y el
 * mismo estado de cámara — procesarTickVerificacion decide tick a tick si
 * está buscando una cara conocida o verificando que gire la cabeza.
 *
 * `onReconocido(trabajador)` se llama tanto cuando una cara conocida pasa el
 * chequeo de vida, como cuando termina de enrolarse una cara nueva (el
 * trabajador llega con `face_descriptor` recién asignado) — igual que en el
 * componente original, donde ambos caminos terminaban en el mismo
 * confirmarTrabajador().
 */
export function useReconocimientoFacial({ activo, trabajadores, bodegaId, onReconocido, setError }) {
  const [camaraActiva, setCamaraActiva] = useState(false);
  const [verificandoVida, setVerificandoVida] = useState(false);
  const [modoVerificacion, setModoVerificacion] = useState('reconocer');
  const [debugFacial, setDebugFacial] = useState({ distancia: null, giro: null, backend: null, msPorLectura: null });
  const [rutManual, setRutManual] = useState('');

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const intervaloDeteccionRef = useRef(null);
  const procesandoDeteccionRef = useRef(false);
  const candidatoRef = useRef({ id: null, veces: 0 });
  const verificacionRef = useRef(null);
  const intentosFallidosRef = useRef({});
  const trabajadoresRef = useRef([]);
  const reintentoCamaraRef = useRef(null);
  const activoRef = useRef(activo);

  useEffect(() => {
    trabajadoresRef.current = trabajadores;
  }, [trabajadores]);

  useEffect(() => {
    activoRef.current = activo;
  }, [activo]);

  const iniciarCamara = async () => {
    if (streamRef.current) return;

    if (reintentoCamaraRef.current) {
      clearTimeout(reintentoCamaraRef.current);
      reintentoCamaraRef.current = null;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;

      // Detecta si la cámara se pierde en pleno uso (se desconecta el USB,
      // el SO se la quita para otra app, etc.): sin esto, el kiosco se
      // queda mostrando "Buscando rostro..." para siempre sin procesar
      // ningún frame, y nadie hay ahí para reiniciarlo a mano.
      stream.getVideoTracks().forEach((track) => {
        track.onended = () => {
          if (streamRef.current === stream) {
            console.warn('La cámara se desconectó — reintentando.');
            detenerCamara();
            programarReintentoCamara();
          }
        };
      });

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
        'No se pudo acceder a la cámara. Reintentando automáticamente — revisa el permiso del navegador. ' +
        'Si el kiosco se abre por IP de red (no localhost/https), el navegador puede bloquear la cámara por ser un origen no seguro.'
      );
      programarReintentoCamara();
    }
  };

  const programarReintentoCamara = () => {
    if (reintentoCamaraRef.current) return;

    reintentoCamaraRef.current = setTimeout(() => {
      reintentoCamaraRef.current = null;
      // Reintenta solo si seguimos activos: si mientras tanto se reconoció
      // a alguien por otra vía o se cambió de pantalla, no tiene sentido
      // volver a prender la cámara acá. Se lee de un ref (no de "activo"
      // cerrado en esta función) porque pueden pasar varios renders entre
      // que se programó este reintento y que efectivamente se dispare.
      if (activoRef.current) iniciarCamara();
    }, RETRASO_REINTENTO_CAMARA_MS);
  };

  const detenerCamara = () => {
    if (intervaloDeteccionRef.current) clearInterval(intervaloDeteccionRef.current);
    intervaloDeteccionRef.current = null;
    procesandoDeteccionRef.current = false;

    if (reintentoCamaraRef.current) {
      clearTimeout(reintentoCamaraRef.current);
      reintentoCamaraRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => {
        t.onended = null;
        t.stop();
      });
      streamRef.current = null;
    }

    setCamaraActiva(false);
    setDebugFacial({ distancia: null, giro: null, backend: null, msPorLectura: null });
  };

  // --- Cámara: arranca/detiene según "activo" (equivalente a fase === 'reconociendo') ---
  useEffect(() => {
    if (activo) {
      iniciarCamara();
    } else {
      detenerCamara();
    }

    return () => detenerCamara();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activo]);

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
        detenerCamara();
        onReconocido(trabajador);
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

      detenerCamara();
      onReconocido({ ...trabajador, face_descriptor: descriptor });
    } catch (err) {
      console.error(err);
      setError('No se pudo registrar tu rostro (requiere conexión la primera vez). Intenta de nuevo cuando haya internet.');
    }
  };

  return {
    videoRef,
    camaraActiva,
    verificandoVida,
    modoVerificacion,
    debugFacial,
    rutManual,
    setRutManual,
    buscarPorRutYEnrolar,
    detenerCamara,
    UMBRAL_DISTANCIA_FACIAL,
    UMBRAL_GIRO_CABEZA,
  };
}
