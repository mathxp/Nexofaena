import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const api = axios.create({
    baseURL: `${API_URL}/api`,
});

api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// ---------------------------------------------------------------------------
// Caché corto de lecturas (GET)
//
// Cada pantalla vuelve a pedir sus datos al montarse, así que ir y volver
// entre pestañas repetía las mismas descargas. Una lectura repetida dentro de
// TTL_CACHE_MS se responde desde memoria al instante, y dos pantallas que
// piden lo mismo a la vez comparten una sola petición.
//
// Nunca muestra datos viejos después de un cambio: cualquier escritura (POST,
// PUT, PATCH, DELETE) vacía el caché completo. También se vacía al iniciar y
// cerrar sesión (ver limpiarCacheApi), para no mezclar datos entre usuarios.
// ---------------------------------------------------------------------------
const TTL_CACHE_MS = 60_000;

// Lecturas que deben ir siempre al servidor.
const SIN_CACHE = [
    '/me/', // identidad del usuario logueado
    '/dashboard/ml-busqueda/', // búsqueda puntual
    'trabajador=', // préstamos pendientes del trabajador en el kiosco
    '/telegram/', // estado de vinculación, cambia desde Telegram
];

const adaptadorRed = axios.getAdapter(axios.defaults.adapter);
const respuestas = new Map();
const enCurso = new Map();

export const limpiarCacheApi = () => {
    respuestas.clear();
};

const copiar = (respuesta, config) => ({ ...respuesta, data: structuredClone(respuesta.data), config });

api.defaults.adapter = async (config) => {
    const metodo = (config.method || 'get').toLowerCase();

    if (metodo !== 'get') {
        try {
            return await adaptadorRed(config);
        } finally {
            limpiarCacheApi();
        }
    }

    const clave = api.getUri(config);
    if (config.sinCache || SIN_CACHE.some((patron) => clave.includes(patron))) {
        return adaptadorRed(config);
    }

    const guardada = respuestas.get(clave);
    if (guardada && guardada.expira > Date.now()) {
        // Copia: si una pantalla modifica la lista recibida, no altera el caché.
        return copiar(guardada.respuesta, config);
    }

    if (enCurso.has(clave)) {
        return copiar(await enCurso.get(clave), config);
    }

    const peticion = adaptadorRed(config);
    enCurso.set(clave, peticion);
    try {
        const respuesta = await peticion;
        respuestas.set(clave, { respuesta, expira: Date.now() + TTL_CACHE_MS });
        return copiar(respuesta, config);
    } finally {
        enCurso.delete(clave);
    }
};

export default api;
