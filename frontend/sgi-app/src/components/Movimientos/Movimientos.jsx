import { useState, useEffect } from 'react';
import {
    FaExchangeAlt, FaPlus, FaHistory, FaExclamationTriangle,
    FaCheckCircle, FaUserShield, FaChevronLeft, FaChevronRight, FaFilter,
} from 'react-icons/fa';
import api from '../../api';
import './Movimientos.css';

const MOVIMIENTOS_POR_PAGINA = 12;

const Movimientos = () => {
    const [movimientos, setMovimientos] = useState([]);
    const [productos, setProductos] = useState([]);
    const [bodegas, setBodegas] = useState([]);

    const [usuarioActual, setUsuarioActual] = useState({
        id: localStorage.getItem('user_id') ? Number(localStorage.getItem('user_id')) : null,
        username: localStorage.getItem('username') || '',
        rol: localStorage.getItem('user_role') || '',
    });

    const [error, setError] = useState('');
    const [exito, setExito] = useState('');

    const [filtroTipo, setFiltroTipo] = useState('');
    const [filtroBodega, setFiltroBodega] = useState('');
    const [paginaActual, setPaginaActual] = useState(1);

    const [formData, setFormData] = useState({
        bodega: '',
        inventario: '',
        tipo_movimiento: 'INGRESO',
        cantidad: '',
        observacion: '',
    });

    useEffect(() => {
        cargarUsuarioActual();
        cargarDatos();
    }, []);

    useEffect(() => { setPaginaActual(1); }, [filtroTipo, filtroBodega]);

    const cargarUsuarioActual = async () => {
        if (usuarioActual.id) return;

        try {
            const res = await api.get('/me/');

            localStorage.setItem('user_id', res.data.id);
            localStorage.setItem('username', res.data.username);
            localStorage.setItem('user_role', res.data.rol_nombre || '');

            setUsuarioActual({
                id: res.data.id,
                username: res.data.username,
                rol: res.data.rol_nombre || '',
            });
        } catch (err) {
            console.error(err);
        }
    };

    const cargarDatos = async () => {
        try {
            const [resMovs, resProds, resBodegas] = await Promise.all([
                api.get('/movimientos/'),
                api.get('/inventario/'),
                api.get('/bodegas/'),
            ]);
            setMovimientos(resMovs.data);
            setProductos(resProds.data);
            setBodegas(resBodegas.data);
            setError('');
        } catch (err) {
            console.error(err);
            setError('Error al cargar la información del servidor.');
        }
    };

    const handleChange = (e) => {
        const { name, value } = e.target;

        setFormData((prev) => ({
            ...prev,
            [name]: value,
            ...(name === 'bodega' ? { inventario: '' } : {}),
        }));
    };

    const productoSeleccionado = productos.find((p) => p.id === parseInt(formData.inventario));

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setExito('');

        if (!usuarioActual.id) {
            setError('⚠️ No se pudo identificar al responsable. Vuelve a iniciar sesión.');
            return;
        }

        try {
            await api.post('/movimientos/', formData);

            setFormData((prev) => ({ ...prev, cantidad: '', observacion: '' }));
            cargarDatos();
            setExito('¡Movimiento de inventario registrado correctamente!');

            setTimeout(() => setExito(''), 3000);
        } catch (err) {
            console.error(err);
            setError(err.response?.data?.detail || 'Error al registrar el movimiento. Verifica los campos requeridos.');
        }
    };

    const renderBadge = (tipo) => {
        if (tipo === 'INGRESO') return <span className="badge-mov badge-ingreso">Ingreso</span>;
        if (tipo === 'SALIDA') return <span className="badge-mov badge-salida">Salida</span>;
        if (tipo === 'DEVOLUCION') return <span className="badge-mov badge-devolucion">Devolución</span>;
        return <span className="badge-mov badge-ajuste">Ajuste</span>;
    };

    const etiquetaCantidad = formData.tipo_movimiento === 'AJUSTE'
        ? 'Nuevo stock exacto (reemplaza el valor actual)'
        : 'Cantidad a mover';

    const movimientosFiltrados = movimientos.filter((mov) => {
        const coincideTipo = filtroTipo ? mov.tipo_movimiento === filtroTipo : true;
        const coincideBodega = filtroBodega ? String(mov.bodega) === String(filtroBodega) : true;
        return coincideTipo && coincideBodega;
    });

    const movimientosOrdenados = [...movimientosFiltrados].sort(
        (a, b) => new Date(b.fecha) - new Date(a.fecha)
    );

    const totalPaginas = Math.max(1, Math.ceil(movimientosOrdenados.length / MOVIMIENTOS_POR_PAGINA));
    const paginaSegura = Math.min(paginaActual, totalPaginas);
    const movimientosPagina = movimientosOrdenados.slice(
        (paginaSegura - 1) * MOVIMIENTOS_POR_PAGINA,
        paginaSegura * MOVIMIENTOS_POR_PAGINA
    );

    return (
        <div className="movimientos-wrapper">
            <h1 className="page-title"><FaExchangeAlt /> Movimientos de Inventario</h1>

            <div className="responsable-banner">
                <FaUserShield />
                <div>
                    <span className="responsable-label">Registrando movimiento como</span>
                    <strong className="responsable-nombre">
                        {usuarioActual.username || 'Usuario no identificado'}
                        {usuarioActual.rol ? ` · ${usuarioActual.rol}` : ''}
                    </strong>
                </div>
            </div>

            {error && <div className="alert-msg alert-error"><FaExclamationTriangle /> {error}</div>}
            {exito && <div className="alert-msg alert-success"><FaCheckCircle /> {exito}</div>}

            {/* FORMULARIO */}
            <div className="form-container">
                <div className="form-header">
                    <FaPlus style={{ color: '#ea580c' }} /> Registrar Nueva Entrada / Salida
                </div>

                <form onSubmit={handleSubmit} className="form-grid">

                    <div className="input-group">
                        <label className="input-label">Tipo de Movimiento</label>
                        <select className="custom-select" name="tipo_movimiento" value={formData.tipo_movimiento} onChange={handleChange} required>
                            <option value="INGRESO">Ingreso (Suma stock)</option>
                            <option value="SALIDA">Salida (Resta stock)</option>
                            <option value="AJUSTE">Ajuste (Reemplaza stock exacto)</option>
                        </select>
                    </div>

                    <div className="input-group">
                        <label className="input-label">Bodega Origen/Destino</label>
                        <select className="custom-select" name="bodega" value={formData.bodega} onChange={handleChange} required>
                            <option value="">-- Seleccione Bodega --</option>
                            {bodegas.map(b => <option key={b.id} value={b.id}>{b.nombre}</option>)}
                        </select>
                    </div>

                    <div className="input-group">
                        <label className="input-label">Producto Afectado</label>
                        <select className="custom-select" name="inventario" value={formData.inventario} onChange={handleChange} required disabled={!formData.bodega}>
                            <option value="">{formData.bodega ? '-- Seleccione Producto --' : 'Primero seleccione bodega'}</option>
                            {productos.filter(p => p.bodega === parseInt(formData.bodega)).map(p => (
                                <option key={p.id} value={p.id}>[{p.codigo}] {p.nombre} (Stock actual: {p.stock_actual})</option>
                            ))}
                        </select>
                        {productoSeleccionado?.es_devolutivo && (
                            <small className="aviso-devolutivo-inline">
                                ⚠️ Este producto es devolutivo. Para entregarlo a un trabajador usa <strong>Entregas</strong>, no Movimientos.
                            </small>
                        )}
                    </div>

                    <div className="input-group">
                        <label className="input-label">{etiquetaCantidad}</label>
                        <input className="form-input" type="number" step="0.01" min="0" name="cantidad" placeholder="Ej: 10" value={formData.cantidad} onChange={handleChange} required />
                    </div>

                    <div className="input-group full-width">
                        <label className="input-label">Observaciones (Opcional)</label>
                        <input className="form-input" type="text" name="observacion" placeholder="Detalle del movimiento" value={formData.observacion} onChange={handleChange} />
                    </div>

                    <div className="full-width" style={{ marginTop: '10px' }}>
                        <button type="submit" className="btn-guardar">
                            Confirmar Movimiento
                        </button>
                    </div>
                </form>
            </div>

            {/* TABLA DE HISTORIAL */}
            <div className="table-section">
                <div className="table-header">
                    <FaHistory style={{ color: '#94a3b8' }} /> Historial de Movimientos

                    <div className="filtros-historial">
                        <FaFilter className="filtro-icon" />
                        <select className="filtro-select" value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
                            <option value="">Todos los tipos</option>
                            <option value="INGRESO">Ingreso</option>
                            <option value="SALIDA">Salida</option>
                            <option value="AJUSTE">Ajuste</option>
                        </select>
                        <select className="filtro-select" value={filtroBodega} onChange={(e) => setFiltroBodega(e.target.value)}>
                            <option value="">Todas las bodegas</option>
                            {bodegas.map(b => <option key={b.id} value={b.id}>{b.nombre}</option>)}
                        </select>
                    </div>
                </div>
                <div className="table-responsive">
                    <table className="styled-table">
                        <thead>
                            <tr>
                                <th>Tipo</th>
                                <th>Producto</th>
                                <th>Bodega</th>
                                <th>Cantidad</th>
                                <th>Stock resultante</th>
                                <th>Responsable</th>
                                <th>Observación</th>
                                <th>Fecha y Hora</th>
                            </tr>
                        </thead>
                        <tbody>
                            {movimientosPagina.length === 0 ? (
                                <tr>
                                    <td colSpan="8" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                                        No hay movimientos que coincidan con el filtro.
                                    </td>
                                </tr>
                            ) : (
                                movimientosPagina.map((mov) => (
                                    <tr key={mov.id}>
                                        <td>{renderBadge(mov.tipo_movimiento)}</td>
                                        <td style={{ fontWeight: '700' }}>{mov.producto_nombre || 'Desconocido'}</td>
                                        <td>{mov.bodega_nombre || 'N/A'}</td>
                                        <td style={{ fontWeight: '900', fontSize: '1.1rem' }}>{mov.cantidad}</td>
                                        <td style={{ color: '#94a3b8' }}>{mov.stock_anterior} → {mov.stock_actual}</td>
                                        <td>{mov.usuario_nombre || 'N/A'}</td>
                                        <td style={{ color: '#94a3b8' }}>{mov.observacion || '—'}</td>
                                        <td style={{ color: '#94a3b8' }}>{new Date(mov.fecha).toLocaleString()}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

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

export default Movimientos;
