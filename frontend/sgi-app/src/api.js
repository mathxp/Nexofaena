import axios from 'axios';

// Usamos import.meta.env.VITE_API_URL para flexibilidad en producción
// Si no existe (estás en local), usará por defecto tu localhost
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api',
});

// Interceptor: Antes de que salga cualquier petición, le pegamos el Token si existe
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

export default api;