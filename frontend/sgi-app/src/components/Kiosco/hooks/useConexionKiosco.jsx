import { useEffect, useState } from 'react';

import { sincronizarEntregasPendientes } from '../../../services/entregasOffline';

/**
 * Antes el estado de conexión solo se revisaba al tocar una acción puntual
 * (retirar un radio, confirmar firma, etc.), así que un trabajador sin señal
 * no tenía forma de saberlo de antemano — se enteraba recién al chocar con
 * un mensaje de error a mitad de flujo. Este hook expone el estado en vivo
 * para un badge siempre visible, y dispara la sincronización de la cola
 * offline apenas vuelve la señal.
 */
export function useConexionKiosco() {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const alConectar = () => {
      setIsOffline(false);
      sincronizarEntregasPendientes();
    };
    const alDesconectar = () => setIsOffline(true);

    window.addEventListener('online', alConectar);
    window.addEventListener('offline', alDesconectar);

    return () => {
      window.removeEventListener('online', alConectar);
      window.removeEventListener('offline', alDesconectar);
    };
  }, []);

  return isOffline;
}
