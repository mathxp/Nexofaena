import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../api';
import './ResetPassword.css';

const ResetPassword = () => {
  const { uid, token } = useParams();
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMensaje('');
    setError('');

    if (!password || !password2) {
      setError('Debe ingresar y repetir la contraseña.');
      return;
    }

    if (password.length < 6) {
      setError('La contraseña debe tener mínimo 6 caracteres.');
      return;
    }

    if (password !== password2) {
      setError('Las contraseñas no coinciden.');
      return;
    }

    try {
      await api.post('/password-reset-confirm/', {
        uid,
        token,
        password,
      });

      setMensaje('Contraseña actualizada correctamente.');

      setTimeout(() => {
        navigate('/');
      }, 1800);
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo actualizar la contraseña.');
    }
  };

  return (
    <div className="password-background">
      <div className="password-card">
        <h2>NUEVA CONTRASEÑA</h2>
        <p>Ingresa tu nueva contraseña para acceder a NexoFaena.</p>

        {error && <div className="password-error">{error}</div>}
        {mensaje && <div className="password-success">{mensaje}</div>}

        <form onSubmit={handleSubmit} className="password-form">
          <input
            type="password"
            placeholder="Nueva contraseña"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <input
            type="password"
            placeholder="Repetir contraseña"
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
          />

          <button type="submit">ACTUALIZAR CONTRASEÑA</button>
        </form>
      </div>
    </div>
  );
};

export default ResetPassword;