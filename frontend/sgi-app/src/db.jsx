import Dexie from 'dexie';

export const db = new Dexie('NexoFaenaLocalDB');

db.version(1).stores({
    entregas_pendientes: '++id, trabajador_id, fecha, sincronizado',
    cache_trabajadores: 'id, rut, nombres, apellido_paterno, cargo',
    cache_inventario: 'id, codigo, nombre, stock_actual',
    cache_usuarios: 'id, username, first_name, last_name'
});

db.version(2).stores({
    entregas_pendientes: '++id, trabajador_id, fecha, sincronizado',
    cache_trabajadores: 'id, rut, nombres, apellido_paterno, cargo',
    cache_inventario: 'id, codigo, nombre, stock_actual',
    cache_usuarios: 'id, username, first_name, last_name',
    conteos_pendientes: '++id, auditoria_id, inventario_id, sincronizado',
});

db.version(3).stores({
    entregas_pendientes: '++id, trabajador_id, fecha, sincronizado',
    cache_trabajadores: 'id, rut, nombres, apellido_paterno, cargo',
    cache_inventario: 'id, codigo, nombre, stock_actual',
    cache_usuarios: 'id, username, first_name, last_name',
    conteos_pendientes: '++id, auditoria_id, inventario_id, sincronizado',
    // Último snapshot sincronizado de reportes agregados, para que la vista
    // degrade bien sin conexión (clave fija por reporte, ej. 'epp_por_turno').
    cache_reportes: 'clave, sincronizado_en',
});

db.version(4).stores({
    entregas_pendientes: '++id, trabajador_id, fecha, sincronizado',
    cache_trabajadores: 'id, rut, nombres, apellido_paterno, cargo',
    cache_inventario: 'id, codigo, nombre, stock_actual',
    cache_usuarios: 'id, username, first_name, last_name',
    conteos_pendientes: '++id, auditoria_id, inventario_id, sincronizado',
    cache_reportes: 'clave, sincronizado_en',
    cache_bodegas: 'id, nombre',
    // Despachos rápidos (ej. agua) registrados sin conexión, a la espera de
    // sincronizarse con el backend cuando vuelva la red.
    despachos_pendientes: '++id, inventario_id, bodega_id, fecha, sincronizado',
});

db.version(5).stores({
    // Despacho Rápido se eliminó del sistema: null borra el object store en
    // los navegadores que ya tenían la versión 4 (Dexie exige bumpear la
    // versión para eliminar una tabla, no alcanza con quitarla del bloque
    // anterior).
    despachos_pendientes: null,
});

db.version(6).stores({
    // Sin cambio de índices: lat/lon/accuracy/capturada_en viajan como
    // columnas no indexadas dentro del mismo registro de
    // entregas_pendientes (Dexie no exige declarar cada campo, solo los
    // que se indexan).
    entregas_pendientes: '++id, trabajador_id, fecha, sincronizado',
});