import { useState, useEffect } from 'react';
import { FaUser, FaEdit, FaTrashAlt, FaCircle, FaSearch, FaUserPlus, FaUsers } from 'react-icons/fa';
import api from '../../api';
import './Trabajadores.css';

const Trabajadores = () => {
    const [trabajadores, setTrabajadores] = useState([]);
    const [error, setError] = useState('');
    
    // Estados para UI
    const [mostrarFormulario, setMostrarFormulario] = useState(false);
    const [modoEdicion, setModoEdicion] = useState(false);
    const [idEdicion, setIdEdicion] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');

    const [formData, setFormData] = useState({
        rut: '', nombres: '', apellido_paterno: '', apellido_materno: '', cargo: '', telefono: '', correo: ''
    });

    useEffect(() => { cargarTrabajadores(); }, []);

    const cargarTrabajadores = async () => {
        try {
            const response = await api.get('/trabajadores/');
            setTrabajadores(response.data);
        } catch (err) { setError('Error al cargar la lista de trabajadores.'); }
    };

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (modoEdicion) {
                await api.put(`/trabajadores/${idEdicion}/`, formData);
            } else {
                await api.post('/trabajadores/', formData);
            }
            limpiarFormulario();
            cargarTrabajadores();
        } catch (err) { setError('Error al guardar. Verifica que el RUT no esté duplicado o los campos incompletos.'); }
    };

    const cargarParaEdicion = (trabajador) => {
        setMostrarFormulario(true);
        setModoEdicion(true);
        setIdEdicion(trabajador.id);
        setFormData({ ...trabajador });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const eliminarTrabajador = async (id) => {
        if (window.confirm("¿Eliminar este trabajador? No podrás hacerlo si tiene entregas asociadas.")) {
            try {
                await api.delete(`/trabajadores/${id}/`);
                cargarTrabajadores();
            } catch (err) { setError('No se puede eliminar. Tiene registros asociados.'); }
        }
    };

    const limpiarFormulario = () => {
        setMostrarFormulario(false);
        setModoEdicion(false);
        setIdEdicion(null);
        setFormData({ rut: '', nombres: '', apellido_paterno: '', apellido_materno: '', cargo: '', telefono: '', correo: '' });
        setError('');
    };

    // Filtro inteligente para la barra de búsqueda
    const trabajadoresFiltrados = trabajadores.filter(t => 
        t.rut.toLowerCase().includes(searchTerm.toLowerCase()) || 
        t.nombres.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.apellido_paterno.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="trabajadores-wrapper">
            <h1 className="page-title"><FaUsers /> Gestión de Trabajadores</h1>
            
            {error && <div className="error-msg">{error}</div>}

            {/* PANEL DE BÚSQUEDA Y ACCIÓN */}
            <div className="action-panel">
                <div className="panel-header"><FaUser /> Directorio de Personal</div>
                
                <div className="search-add-container">
                    <div className="search-group">
                        <label>Buscar por RUT o Apellido</label>
                        <div className="search-input-wrapper">
                            <span className="search-icon-box"><FaSearch /></span>
                            <input 
                                type="text" 
                                placeholder="Ej: 12.345.678-k" 
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>

                    <button 
                        className="btn-agregar-main"
                        onClick={() => { limpiarFormulario(); setMostrarFormulario(true); }}
                    >
                        <FaUserPlus /> AGREGAR TRABAJADOR
                    </button>
                </div>
            </div>

            {/* FORMULARIO DESPLEGABLE */}
            {mostrarFormulario && (
                <div className={`form-container ${modoEdicion ? 'edit-mode' : ''}`}>
                    <h3 className="form-title">
                        {modoEdicion ? 'Editar Registro de Trabajador' : 'Registrar Nuevo Trabajador'}
                    </h3>
                    <form onSubmit={handleSubmit}>
                        <div className="form-grid">
                            
                            <div className="input-group">
                                <label className="input-label">RUT del Trabajador</label>
                                <input type="text" name="rut" placeholder="Ej: 12345678-9" value={formData.rut} onChange={handleChange} required className="form-input" disabled={modoEdicion} />
                            </div>

                            <div className="input-group">
                                <label className="input-label">Nombres</label>
                                <input type="text" name="nombres" placeholder="Nombres" value={formData.nombres} onChange={handleChange} required className="form-input" />
                            </div>

                            <div className="input-group">
                                <label className="input-label">Apellido Paterno</label>
                                <input type="text" name="apellido_paterno" placeholder="Apellido Paterno" value={formData.apellido_paterno} onChange={handleChange} required className="form-input" />
                            </div>

                            <div className="input-group">
                                <label className="input-label">Apellido Materno</label>
                                <input type="text" name="apellido_materno" placeholder="Apellido Materno (Opcional)" value={formData.apellido_materno} onChange={handleChange} className="form-input" />
                            </div>

                            <div className="input-group">
                                <label className="input-label">Cargo</label>
                                <input type="text" name="cargo" placeholder="Ej: Operador de Maquinaria" value={formData.cargo} onChange={handleChange} required className="form-input" />
                            </div>

                            <div className="input-group">
                                <label className="input-label">Teléfono</label>
                                <input type="text" name="telefono" placeholder="Ej: +569 12345678" value={formData.telefono} onChange={handleChange} className="form-input" />
                            </div>

                            <div className="input-group full-width">
                                <label className="input-label">Correo Electrónico</label>
                                <input type="email" name="correo" placeholder="correo@ejemplo.com" value={formData.correo} onChange={handleChange} className="form-input" />
                            </div>

                        </div>
                        
                        <div className="form-actions">
                            <button type="submit" className="btn-guardar">
                                {modoEdicion ? 'Actualizar Trabajador' : 'Guardar Trabajador'}
                            </button>
                            <button type="button" onClick={limpiarFormulario} className="btn-cancelar">
                                Cancelar
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {/* TABLA DE DATOS */}
            <div className="table-responsive">
                <table className="styled-table">
                    <thead>
                        <tr>
                            <th>RUT</th>
                            <th>Nombre Completo</th>
                            <th>Cargo</th>
                            <th>Estado</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trabajadoresFiltrados.length === 0 ? (
                            <tr><td colSpan="5" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>No se encontraron trabajadores.</td></tr>
                        ) : (
                            trabajadoresFiltrados.map((t) => (
                                <tr key={t.id}>
                                    <td><strong>{t.rut}</strong></td>
                                    <td>{t.nombres} {t.apellido_paterno} {t.apellido_materno}</td>
                                    <td>{t.cargo}</td>
                                    <td>
                                        <div className="estado-badge">
                                            <FaCircle className="dot-activo" /> Activo
                                        </div>
                                    </td>
                                    <td>
                                        <div className="action-buttons">
                                            <button onClick={() => cargarParaEdicion(t)} className="btn-icon btn-edit" title="Editar">
                                                <FaEdit />
                                            </button>
                                            <button onClick={() => eliminarTrabajador(t.id)} className="btn-icon btn-delete" title="Eliminar">
                                                <FaTrashAlt />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

        </div>
    );
};

export default Trabajadores;