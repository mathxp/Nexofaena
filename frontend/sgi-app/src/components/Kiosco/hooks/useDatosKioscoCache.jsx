import { useState } from 'react';

import api from '../../../api';
import { db } from '../../../db';

/**
 * Trabajadores, inventario, bodegas y unidades-activo que el kiosco necesita
 * para operar. Se piden al backend y se guardan en IndexedDB de paso; si no
 * hay conexión (arranque en frío sin señal), cae al último dato cacheado en
 * el dispositivo en vez de dejar el kiosco sin nada que mostrar.
 *
 * Las unidades (radios, etc.) no se cachean offline a propósito: igual que
 * en Entregas.jsx, asignar un equipo devolutivo exige conexión para no
 * arriesgarse a entregar el mismo radio a dos personas.
 */
export function useDatosKioscoCache() {
  const [trabajadores, setTrabajadores] = useState([]);
  const [inventario, setInventario] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [unidadesDisponibles, setUnidadesDisponibles] = useState([]);

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

  return { trabajadores, inventario, bodegas, unidadesDisponibles, cargarDatos };
}
