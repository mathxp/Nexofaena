import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../api';
import './OlvidePassword.css';

const OlvidePassword = () => {
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMensaje('');
    setError('');

    if (!email.trim()) {
      setError('Ingrese su correo.');
      return;
    }

    try {
      await api.post('/password-reset/', {
        email: email.trim(),
      });

      setMensaje('Si el correo existe, se enviará un enlace de recuperación.');
    } catch {
      setError('No se pudo solicitar la recuperación.');
    }
  };

  return (
    <div className="password-background">
      <div className="password-card">
        <h2>RECUPERAR CONTRASEÑA</h2>
        <p>Ingresa tu correo para recibir un enlace de recuperación.</p>

        {error && <div className="password-error">{error}</div>}
        {mensaje && <div className="password-success">{mensaje}</div>}

        <form onSubmit={handleSubmit} className="password-form">
          <input
            type="email"
            placeholder="Correo electrónico"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <button type="submit">ENVIAR ENLACE</button>

          <button
            type="button"
            className="btn-volver"
            onClick={() => navigate('/')}
          >
            Volver al login
          </button>
        </form>
      </div>
    </div>
  );
};

export default OlvidePassword;