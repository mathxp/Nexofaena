import axios from 'axios';

// Creamos una instancia de Axios con la URL de tu backend
const api = axios.create({
    baseURL: 'http://127.0.0.1:8000/api',
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