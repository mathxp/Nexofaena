import api from '../api';
import { db } from '../db';

/**
 * Reenvía al backend las entregas que quedaron guardadas localmente
 * mientras no había conexión. Se llama al reconectar (evento 'online') y
 * al montar Entregas.jsx.
 */
export async function sincronizarEntregasPendientes() {
  const pendientes = await db.entregas_pendientes.where({ sincronizado: 0 }).toArray();
  if (pendientes.length === 0) return 0;

  let sincronizadas = 0;

  for (const entrega of pendientes) {
    try {
      await api.post('/entregas-epp/', {
        trabajador: entrega.trabajador_id,
        usuario: entrega.usuario_id,
        bodega: entrega.bodega_id,
        firma_base64: entrega.firma_base64,
        observacion: entrega.observacion || 'Entrega sincronizada desde modo offline',
        estado: 'COMPLETADA',
        // La coordenada viaja tal cual se capturó en terreno al momento de
        // la entrega, no la del dispositivo al reconectar: eso es lo que
        // la hace válida como evidencia de auditoría.
        latitud: entrega.latitud,
        longitud: entrega.longitud,
        precision_metros: entrega.precision_metros,
        geolocalizacion_capturada_en: entrega.geolocalizacion_capturada_en,
        detalles: Object.keys(entrega.productos).map((productoId) => ({
          inventario: parseInt(productoId),
          cantidad: entrega.productos[productoId],
          talla: 'N/A',
        })),
      });

      await db.entregas_pendientes.delete(entrega.id);
      sincronizadas += 1;
    } catch (err) {
      console.error('Error sincronizando entrega:', err);
    }
  }

  return sincronizadas;
}
