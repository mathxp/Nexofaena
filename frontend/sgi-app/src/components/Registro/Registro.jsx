import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../api';
import './Registro.css';

const Registro = () => {
  const navigate = useNavigate();

  const [roles, setRoles] = useState([]);
  const [error, setError] = useState('');
  const [exito, setExito] = useState('');

  const [formData, setFormData] = useState({
    token: '',
    username: '',
    rut: '',
    email: '',
    first_name: '',
    last_name: '',
    telefono: '',
    rol: '',
    password: '',
    password2: '',
  });

  useEffect(() => {
    cargarRoles();
  }, []);

  const cargarRoles = async () => {
    try {
      const response = await api.get('/roles/');
      setRoles(response.data);
    } catch {
      setRoles([]);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const validar = () => {
    if (!formData.token.trim()) return 'Debe ingresar el token de invitación.';
    if (!formData.username.trim()) return 'Debe ingresar un usuario.';
    if (!formData.rut.trim()) return 'Debe ingresar el RUT.';
    if (!formData.rol) return 'Debe seleccionar un rol.';
    if (!formData.password) return 'Debe ingresar una contraseña.';
    if (formData.password.length < 6) return 'La contraseña debe tener mínimo 6 caracteres.';
    if (formData.password !== formData.password2) return 'Las contraseñas no coinciden.';

    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setExito('');

    const errorValidacion = validar();
    if (errorValidacion) {
      setError(errorValidacion);
      return;
    }

    try {
      await api.post('/register/', {
        token: formData.token.trim(),
        username: formData.username.trim(),
        rut: formData.rut.trim(),
        email: formData.email.trim(),
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        telefono: formData.telefono.trim(),
        rol: formData.rol,
        password: formData.password,
      });

      setExito('Usuario registrado correctamente. Ya puedes iniciar sesión.');

      setTimeout(() => {
        navigate('/');
      }, 1800);
    } catch (err) {
      console.error(err);

      const data = err.response?.data;

      if (typeof data === 'string') {
        setError(data);
      } else if (data?.non_field_errors) {
        setError(data.non_field_errors[0]);
      } else if (data) {
        const firstKey = Object.keys(data)[0];
        const value = data[firstKey];
        setError(Array.isArray(value) ? value[0] : String(value));
      } else {
        setError('No se pudo registrar el usuario.');
      }
    }
  };

  return (
    <div className="registro-background">
      <div className="registro-card">
        <h2>REGISTRO SEGURO</h2>
        <p>Crear usuario mediante token de invitación</p>

        {error && <div className="registro-error">{error}</div>}
        {exito && <div className="registro-success">{exito}</div>}

        <form onSubmit={handleSubmit} className="registro-form">
          <input
            name="token"
            placeholder="Token de invitación"
            value={formData.token}
            onChange={handleChange}
          />

          <input
            name="username"
            placeholder="Usuario"
            value={formData.username}
            onChange={handleChange}
          />

          <input
            name="rut"
            placeholder="RUT"
            value={formData.rut}
            onChange={handleChange}
          />

          <input
            name="email"
            type="email"
            placeholder="Correo"
            value={formData.email}
            onChange={handleChange}
          />

          <input
            name="first_name"
            placeholder="Nombre"
            value={formData.first_name}
            onChange={handleChange}
          />

          <input
            name="last_name"
            placeholder="Apellido"
            value={formData.last_name}
            onChange={handleChange}
          />

          <input
            name="telefono"
            placeholder="Teléfono"
            value={formData.telefono}
            onChange={handleChange}
          />

          <select name="rol" value={formData.rol} onChange={handleChange}>
            <option value="">Seleccione rol</option>
            {roles.map((rol) => (
              <option key={rol.id} value={rol.id}>
                {rol.nombre}
              </option>
            ))}
          </select>

          <input
            name="password"
            type="password"
            placeholder="Contraseña"
            value={formData.password}
            onChange={handleChange}
          />

          <input
            name="password2"
            type="password"
            placeholder="Repetir contraseña"
            value={formData.password2}
            onChange={handleChange}
          />

          <button type="submit">CREAR CUENTA</button>

          <button type="button" className="btn-volver" onClick={() => navigate('/')}>
            Volver al login
          </button>
        </form>
      </div>
    </div>
  );
};

export default Registro;