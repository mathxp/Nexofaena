import { lazy } from 'react';

// Cada deploy cambia el hash de los chunks (Dashboard-DgFe1133.js, ...) y el
// service worker (autoUpdate) borra los viejos. Quien tenía la app abierta
// sigue con el index anterior, y al navegar a una ruta que aún no cargó pide
// un chunk que ya no existe: "error loading dynamically imported module".
// Recargar una vez trae el index nuevo y resuelve. La marca en sessionStorage
// evita un bucle de recargas si el chunk falla por otra razón (ej. sin red).
const CLAVE_RECARGA = 'nexofaena:recarga-por-chunk';
const VENTANA_MS = 10_000;

const leerMarca = () => {
  try {
    return Number(sessionStorage.getItem(CLAVE_RECARGA)) || 0;
  } catch {
    return 0;
  }
};

const escribirMarca = (valor) => {
  try {
    if (valor) sessionStorage.setItem(CLAVE_RECARGA, String(valor));
    else sessionStorage.removeItem(CLAVE_RECARGA);
  } catch {
    // Sin sessionStorage (modo privado estricto): igual se intenta recargar.
  }
};

const lazyConRecarga = (importar) =>
  lazy(async () => {
    try {
      const modulo = await importar();
      escribirMarca(null);
      return modulo;
    } catch (error) {
      const recargoHacePoco = Date.now() - leerMarca() < VENTANA_MS;

      if (!recargoHacePoco && navigator.onLine !== false) {
        escribirMarca(Date.now());
        window.location.reload();
        // Promesa que no resuelve: mantiene el Suspense mientras recarga.
        return new Promise(() => {});
      }

      throw error;
    }
  });

export default lazyConRecarga;
