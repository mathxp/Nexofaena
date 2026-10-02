import { useEffect, useRef } from 'react';

/**
 * Mantiene la pantalla del kiosco siempre encendida. Un kiosco desatendido
 * no sirve si el dispositivo apaga la pantalla solo a mitad de turno: nadie
 * hay ahí para tocarla y despertarla. El Wake Lock se libera solo cuando la
 * pestaña pasa a segundo plano (ej. se bloquea el dispositivo) — hay que
 * volver a pedirlo cuando vuelve a primer plano, si no queda perdido para el
 * resto de la sesión.
 */
export function useWakeLock() {
  const wakeLockRef = useRef(null);

  useEffect(() => {
    const solicitarWakeLock = async () => {
      try {
        if ('wakeLock' in navigator) {
          wakeLockRef.current = await navigator.wakeLock.request('screen');
        }
      } catch (err) {
        // No soportado, o el navegador lo negó (ej. batería baja en
        // algunos Android) — el kiosco debe seguir funcionando igual,
        // solo sin esta protección extra.
        console.warn('No se pudo mantener la pantalla encendida:', err);
      }
    };

    solicitarWakeLock();

    const alVolverAPrimerPlano = () => {
      if (document.visibilityState === 'visible') solicitarWakeLock();
    };
    document.addEventListener('visibilitychange', alVolverAPrimerPlano);

    return () => {
      document.removeEventListener('visibilitychange', alVolverAPrimerPlano);
      wakeLockRef.current?.release().catch(() => {});
      wakeLockRef.current = null;
    };
  }, []);
}
