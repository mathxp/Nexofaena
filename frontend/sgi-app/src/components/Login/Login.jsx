çimport { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    FaUserAlt,
    FaLock,
    FaEye,
    FaEyeSlash
} from 'react-icons/fa';

import api from '../../api';
import './Login.css';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');

    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');

        try {
            const response = await api.post('/token/', {
                username,
                password
            });

            localStorage.setItem('access_token', response.data.access);
            localStorage.setItem('refresh_token', response.data.refresh);

            localStorage.setItem('user_role', 'Administrador');
            localStorage.setItem('username', username);

            navigate('/dashboard');

        } catch (err) {
            console.error(err);
            setError('Credenciales incorrectas. Intenta nuevamente.');
        }
    };

    return (
        <div className="login-background">
            <div className="login-overlay"></div>

            <div className="login-card">
                <div className="login-logo-container">
                    <img
                        src="/logo.png"
                        alt="NexoFaena Logo"
                        className="login-logo"
                    />
                </div>

                <h2 className="login-title">INICIAR SESIÓN</h2>

                <p className="login-subtitle">
                    Por favor ingrese sus credenciales
                    <br />
                    (Bodeguero, Supervisor, Operador o Administrador)
                </p>

                {error && <div className="login-error">{error}</div>}

                <form onSubmit={handleLogin} className="login-form">
                    <div className="input-group">
                        <div className="input-header">Usuario</div>

                        <div className="input-body">
                            <FaUserAlt className="input-icon" />

                            <input
                                type="text"
                                placeholder="Ingrese su usuario"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                className="login-input"
                            />
                        </div>
                    </div>

                    <div className="input-group">
                        <div className="input-header">Contraseña</div>

                        <div className="input-body">
                            <FaLock className="input-icon" />

                            <input
                                type={showPassword ? 'text' : 'password'}
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                className="login-input"
                            />

                            <button
                                type="button"
                                className="eye-button"
                                onClick={() => setShowPassword(!showPassword)}
                            >
                                {showPassword ? <FaEyeSlash /> : <FaEye />}
                            </button>
                        </div>
                    </div>

                    <div className="forgot-password">
                        <span
                            className="forgot-link"
                            onClick={() => navigate('/forgot-password')}
                        >
                            ¿Olvidaste tu contraseña?
                        </span>
                    </div>

                    <button type="submit" className="login-submit-btn">
                        INGRESAR
                    </button>
                </form>

                <div className="login-footer">
                    <p>NEXOFAENA SGI</p>
                </div>
            </div>
        </div>
    );
};

export default Login;