import { useEffect } from 'react';

import api from '../../../api';

// Render (plan gratis) duerme el servidor tras 15 min sin tráfico. Con un
// aviso cada 10 min nunca llega a dormirse mientras el kiosco esté abierto.
const INTERVALO_MS = 10 * 60 * 1000;

/**
 * Mantiene despierto el servidor mientras el kiosco está abierto.
 *
 * Sin esto, tras un rato sin uso, el primer trabajador reconocido esperaba
 * cerca de un minuto (el servidor arrancando) antes de ver el menú. El
 * primer aviso sale apenas se abre el kiosco, mientras cargan los modelos
 * faciales, para que el servidor ya esté listo cuando llegue alguien.
 */
export function useServidorDespierto() {
  useEffect(() => {
    const avisar = () => {
      if (!navigator.onLine) return;
      api.get('/salud/', { sinCache: true }).catch(() => {});
    };

    avisar();
    const intervalo = setInterval(avisar, INTERVALO_MS);
    window.addEventListener('online', avisar);

    return () => {
      clearInterval(intervalo);
      window.removeEventListener('online', avisar);
    };
  }, []);
}
