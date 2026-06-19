import Dexie from 'dexie';

export const db = new Dexie('NexoFaenaLocalDB');

db.version(1).stores({
    entregas_pendientes: '++id, trabajador_id, fecha, sincronizado',
    cache_trabajadores: 'id, rut, nombres, apellido_paterno, cargo', 
    cache_inventario: 'id, codigo, nombre, stock_actual',
    cache_usuarios: 'id, username, first_name, last_name'
});