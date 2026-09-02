import { useState, useEffect } from 'react';
import {
    FaUser, FaEdit, FaTrashAlt, FaCircle, FaSearch,
    FaUserPlus, FaUsers, FaUndo, FaChevronLeft, FaChevronRight,
} from 'react-icons/fa';
import api from '../../api';
import './Trabajadores.css';

const TRABAJADORES_POR_PAGINA = 12;

const estadoInicial = {
    rut: '', nombres: '', apellido_paterno: '', apellido_materno: '',
    cargo: '', telefono: '', correo: '', fecha_ingreso: '',
};

const Trabajadores = () => {
    const [trabajadores, setTrabajadores] = useState([]);
    const [error, setError] = useState('');

    const [mostrarFormulario, setMostrarFormulario] = useState(false);
    const [modoEdicion, setModoEdicion] = useState(false);
    const [idEdicion, setIdEdicion] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [filtroEstado, setFiltroEstado] = useState('activos');
    const [paginaActual, setPaginaActual] = useState(1);

    const [formData, setFormData] = useState(estadoInicial);

    useEffect(() => { cargarTrabajadores(); }, []);

    useEffect(() => { setPaginaActual(1); }, [searchTerm, filtroEstado]);

    const cargarTrabajadores = async () => {
        try {
            const response = await api.get('/trabajadores/');
            setTrabajadores(response.data);
            setError('');
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
        } catch (err) {
            const data = err.response?.data;
            const detalle = data?.detail || data?.rut?.[0] || data?.correo?.[0];
            setError(detalle || 'Error al guardar. Verifica que el RUT no esté duplicado o los campos incompletos.');
        }
    };

    const cargarParaEdicion = (trabajador) => {
        setMostrarFormulario(true);
        setModoEdicion(true);
        setIdEdicion(trabajador.id);
        setFormData({
            rut: trabajador.rut,
            nombres: trabajador.nombres,
            apellido_paterno: trabajador.apellido_paterno,
            apellido_materno: trabajador.apellido_materno || '',
            cargo: trabajador.cargo,
            telefono: trabajador.telefono || '',
            correo: trabajador.correo || '',
            fecha_ingreso: trabajador.fecha_ingreso || '',
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const desactivarTrabajador = async (id) => {
        if (window.confirm("¿Desactivar este trabajador? Podrás reactivarlo más adelante.")) {
            try {
                await api.delete(`/trabajadores/${id}/`);
                cargarTrabajadores();
            } catch (err) {
                setError(err.response?.data?.detail || 'No se puede desactivar. Tiene registros asociados.');
            }
        }
    };

    const reactivarTrabajador = async (trabajador) => {
        try {
            await api.patch(`/trabajadores/${trabajador.id}/`, { activo: true });
            cargarTrabajadores();
        } catch (err) {
            setError(err.response?.data?.detail || 'No se pudo reactivar al trabajador.');
        }
    };

    const limpiarFormulario = () => {
        setMostrarFormulario(false);
        setModoEdicion(false);
        setIdEdicion(null);
        setFormData(estadoInicial);
        setError('');
    };

    const texto = searchTerm.toLowerCase();

    const trabajadoresFiltrados = trabajadores.filter((t) => {
        const coincideTexto =
            t.rut.toLowerCase().includes(texto) ||
            t.nombres.toLowerCase().includes(texto) ||
            t.apellido_paterno.toLowerCase().includes(texto) ||
            t.cargo?.toLowerCase().includes(texto);

        const coincideEstado =
            filtroEstado === 'todos' ? true : filtroEstado === 'activos' ? t.activo : !t.activo;

        return coincideTexto && coincideEstado;
    });

    const totalPaginas = Math.max(1, Math.ceil(trabajadoresFiltrados.length / TRABAJADORES_POR_PAGINA));
    const paginaSegura = Math.min(paginaActual, totalPaginas);
    const trabajadoresPagina = trabajadoresFiltrados.slice(
        (paginaSegura - 1) * TRABAJADORES_POR_PAGINA,
        paginaSegura * TRABAJADORES_POR_PAGINA
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
                        <label>Buscar por RUT, nombre o cargo</label>
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

                    <div className="search-group filtro-estado-group">
                        <label>Estado</label>
                        <select
                            className="filtro-estado-select"
                            value={filtroEstado}
                            onChange={(e) => setFiltroEstado(e.target.value)}
                        >
                            <option value="activos">Solo activos</option>
                            <option value="inactivos">Solo inactivos</option>
                            <option value="todos">Todos</option>
                        </select>
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
                        <div className="grid-form">

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

                            <div className="input-group">
                                <label className="input-label">Fecha de Ingreso</label>
                                <input type="date" name="fecha_ingreso" value={formData.fecha_ingreso} onChange={handleChange} className="form-input" />
                            </div>

                            <div className="input-group">
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
                        {trabajadoresPagina.length === 0 ? (
                            <tr><td colSpan="5" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>No se encontraron trabajadores.</td></tr>
                        ) : (
                            trabajadoresPagina.map((t) => (
                                <tr key={t.id} className={!t.activo ? 'fila-inactiva' : ''}>
                                    <td><strong>{t.rut}</strong></td>
                                    <td>{t.nombres} {t.apellido_paterno} {t.apellido_materno}</td>
                                    <td>{t.cargo}</td>
                                    <td>
                                        <div className="estado-badge">
                                            {t.activo ? (
                                                <><FaCircle className="dot-activo" /> Activo</>
                                            ) : (
                                                <><FaCircle className="dot-inactivo" /> Inactivo</>
                                            )}
                                        </div>
                                    </td>
                                    <td>
                                        <div className="action-buttons">
                                            <button onClick={() => cargarParaEdicion(t)} className="btn-icon btn-edit" title="Editar">
                                                <FaEdit />
                                            </button>
                                            {t.activo ? (
                                                <button onClick={() => desactivarTrabajador(t.id)} className="btn-icon btn-delete" title="Desactivar">
                                                    <FaTrashAlt />
                                                </button>
                                            ) : (
                                                <button onClick={() => reactivarTrabajador(t)} className="btn-icon btn-reactivar" title="Reactivar">
                                                    <FaUndo />
                                                </button>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>

                {totalPaginas > 1 && (
                    <div className="paginacion">
                        <button
                            className="btn-paginacion"
                            onClick={() => setPaginaActual((p) => Math.max(1, p - 1))}
                            disabled={paginaSegura === 1}
                        >
                            <FaChevronLeft /> Anterior
                        </button>

                        <span className="paginacion-info">Página {paginaSegura} de {totalPaginas}</span>

                        <button
                            className="btn-paginacion"
                            onClick={() => setPaginaActual((p) => Math.min(totalPaginas, p + 1))}
                            disabled={paginaSegura === totalPaginas}
                        >
                            Siguiente <FaChevronRight />
                        </button>
                    </div>
                )}
            </div>

        </div>
    );
};

export default Trabajadores;
