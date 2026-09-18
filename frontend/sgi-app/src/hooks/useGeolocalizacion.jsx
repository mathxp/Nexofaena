import { useCallback, useState } from 'react';

// Alta precisión (GPS del chip, no solo triangulación por wifi/celda): clave
// para que la coordenada sirva como evidencia de auditoría real.
const OPCIONES_GPS = {
  enableHighAccuracy: true,
  timeout: 8000,
  maximumAge: 30000,
};

const mensajeError = (err) => {
  switch (err.code) {
    case err.PERMISSION_DENIED:
      return 'Permiso de ubicación denegado. Actívalo en el navegador para dejar registro de auditoría.';
    case err.POSITION_UNAVAILABLE:
      return 'Ubicación no disponible (sin señal GPS en este punto).';
    case err.TIMEOUT:
      return 'Tiempo de espera agotado al obtener la ubicación.';
    default:
      return 'No se pudo obtener la ubicación del dispositivo.';
  }
};

/**
 * Captura la coordenada GPS del dispositivo para dejar evidencia inmutable
 * de auditoría en cada entrega (SERNAC/SERNATUR/MINSAL/Mandante).
 *
 * Funciona igual online u offline: geolocation.getCurrentPosition es una API
 * del navegador/SO, no depende de red. Si falla o el usuario niega el
 * permiso, resuelve `null` en vez de lanzar: la entrega debe poder
 * completarse igual (con firma) aunque el GPS no esté disponible.
 */
export function useGeolocalizacion() {
  const [estado, setEstado] = useState('inactivo'); // inactivo | capturando | ok | error
  const [error, setError] = useState('');

  const capturar = useCallback(() => {
    return new Promise((resolve) => {
      if (!('geolocation' in navigator)) {
        setEstado('error');
        setError('Este dispositivo no soporta geolocalización.');
        resolve(null);
        return;
      }

      setEstado('capturando');
      setError('');

      navigator.geolocation.getCurrentPosition(
        (posicion) => {
          const punto = {
            latitud: posicion.coords.latitude,
            longitud: posicion.coords.longitude,
            precision_metros: posicion.coords.accuracy,
            geolocalizacion_capturada_en: new Date().toISOString(),
          };

          setEstado('ok');
          resolve(punto);
        },
        (err) => {
          setEstado('error');
          setError(mensajeError(err));
          resolve(null);
        },
        OPCIONES_GPS
      );
    });
  }, []);

  return { capturar, estado, error };
}
