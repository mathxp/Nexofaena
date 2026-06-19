import { useState, useEffect } from 'react';
import { FaSearch, FaEdit, FaTrashAlt, FaExclamationTriangle, FaBoxOpen } from 'react-icons/fa';
import api from '../../api';
import './Inventario.css';

const Inventario = () => {
    const [productos, setProductos] = useState([]);
    const [bodegas, setBodegas] = useState([]);
    const [movimientos, setMovimientos] = useState([]); // Para la tabla inferior
    const [error, setError] = useState('');
    
    // UI States
    const [mostrarFormulario, setMostrarFormulario] = useState(false);
    const [modoEdicion, setModoEdicion] = useState(false);
    const [idEdicion, setIdEdicion] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [tabActiva, setTabActiva] = useState('EPP'); // 'EPP' o 'CONSUMIBLES'

    const [formData, setFormData] = useState({
        codigo: '', nombre: '', descripcion: '', unidad_medida: '', stock_minimo: 0, stock_actual: 0, bodega: ''
    });

    useEffect(() => {
        cargarDatos();
    }, []);

    const cargarDatos = async () => {
        try {
            // Intentamos cargar también los movimientos si la ruta existe
            const [resProductos, resBodegas, resMovs] = await Promise.all([
                api.get('/inventario/'), 
                api.get('/bodegas/'),
                api.get('/movimientos/').catch(() => ({ data: [] })) // Fallback si no existe la ruta aún
            ]);
            setProductos(resProductos.data);
            setBodegas(resBodegas.data);
            setMovimientos(resMovs.data);
        } catch (err) {
            setError('Error al cargar datos del servidor.');
        }
    };

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (modoEdicion) await api.put(`/inventario/${idEdicion}/`, formData);
            else await api.post('/inventario/', formData);
            
            limpiarFormulario();
            cargarDatos();
        } catch (err) { setError('Error al guardar el producto. Verifica que el código no esté duplicado.'); }
    };

    const cargarParaEdicion = (producto) => {
        setMostrarFormulario(true);
        setModoEdicion(true);
        setIdEdicion(producto.id);
        setFormData({
            codigo: producto.codigo, nombre: producto.nombre, descripcion: producto.descripcion || '',
            unidad_medida: producto.unidad_medida, stock_minimo: producto.stock_minimo,
            stock_actual: producto.stock_actual, bodega: producto.bodega
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const eliminarProducto = async (id) => {
        if (window.confirm("¿Eliminar este producto? Esto no se puede deshacer.")) {
            try {
                await api.delete(`/inventario/${id}/`);
                cargarDatos();
            } catch (err) { setError('No se puede eliminar. Tiene movimientos asociados.'); }
        }
    };

    const limpiarFormulario = () => {
        setMostrarFormulario(false);
        setModoEdicion(false);
        setIdEdicion(null);
        setFormData({ codigo: '', nombre: '', descripcion: '', unidad_medida: '', stock_minimo: 0, stock_actual: 0, bodega: '' });
        setError('');
    };

    // Filtro por Búsqueda
    const productosFiltrados = productos.filter(p => 
        p.codigo.toLowerCase().includes(searchTerm.toLowerCase()) || 
        p.nombre.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Lógica para el Badge de Estado
    const obtenerEstadoUI = (actual, minimo) => {
        const act = parseFloat(actual);
        const min = parseFloat(minimo);
        if (act < min) return <span className="badge badge-critico">Crítico</span>;
        if (act === min) return <span className="badge badge-alerta">Alerta Stock Bajo</span>;
        return <span className="badge badge-optimo">Óptimo</span>;
    };

    return (
        <div className="inventario-wrapper">
            <h1 className="page-title">GESTIÓN DE INVENTARIO / BODEGA</h1>
            
            {error && <div style={{ background: '#fef2f2', color: '#dc3545', padding: '15px', borderRadius: '8px', marginBottom: '20px', fontWeight: 'bold' }}>{error}</div>}

            {/* PESTAÑAS SIMULADAS (Igual a la imagen) */}
            <div className="tabs-container">
                <button className={`tab-btn ${tabActiva === 'EPP' ? 'active' : ''}`} onClick={() => setTabActiva('EPP')}>
                    Lista de EPP
                </button>
                <button className={`tab-btn ${tabActiva === 'CONSUMIBLES' ? 'active' : ''}`} onClick={() => setTabActiva('CONSUMIBLES')}>
                    Consumibles
                </button>
            </div>

            {/* BARRA DE BÚSQUEDA Y BOTÓN AGREGAR */}
            <div className="action-panel">
                <div className="search-group">
                    <span className="search-icon"><FaSearch /></span>
                    <input 
                        type="text" 
                        placeholder="Buscar por Ítem o Código..." 
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <button className="btn-agregar-main" onClick={() => { limpiarFormulario(); setMostrarFormulario(true); }}>
                    ➕ AGREGAR PRODUCTO
                </button>
            </div>

            {/* FORMULARIO OCULTO POR DEFECTO */}
            {mostrarFormulario && (
                <div className={`form-container ${modoEdicion ? 'edit-mode' : ''}`}>
                    <h3 style={{ color: modoEdicion ? '#b45309' : '#0f172a', marginBottom: '15px' }}>
                        {modoEdicion ? '✏️ Editar Producto' : '➕ Registrar Nuevo Producto'}
                    </h3>
                    <form onSubmit={handleSubmit}>
                        <div className="form-grid">
                            <input type="text" name="codigo" placeholder="Código (Ej: P-001)" value={formData.codigo} onChange={handleChange} required className="form-input" disabled={modoEdicion} />
                            <input type="text" name="nombre" placeholder="Nombre del Producto" value={formData.nombre} onChange={handleChange} required className="form-input" />
                            
                            <select name="bodega" value={formData.bodega} onChange={handleChange} required className="form-input">
                                <option value="">-- Selecciona Bodega --</option>
                                {bodegas.map(b => <option key={b.id} value={b.id}>{b.nombre}</option>)}
                            </select>

                            <input type="text" name="unidad_medida" placeholder="Unidad (Ej: Unidades, Pares)" value={formData.unidad_medida} onChange={handleChange} required className="form-input" />
                            
                            <div>
                                <label style={{fontSize:'0.8rem', fontWeight:'bold', color:'#666'}}>Stock Actual</label>
                                <input type="number" step="0.01" name="stock_actual" value={formData.stock_actual} onChange={handleChange} required className="form-input" disabled={modoEdicion} />
                            </div>
                            
                            <div>
                                <label style={{fontSize:'0.8rem', fontWeight:'bold', color:'#666'}}>Stock Mínimo (Alerta)</label>
                                <input type="number" step="0.01" name="stock_minimo" value={formData.stock_minimo} onChange={handleChange} required className="form-input" />
                            </div>
                        </div>
                        
                        <div className="form-actions">
                            <button type="submit" className="btn-guardar">{modoEdicion ? 'Actualizar' : 'Guardar Datos'}</button>
                            <button type="button" onClick={limpiarFormulario} className="btn-cancelar">Cancelar</button>
                        </div>
                    </form>
                </div>
            )}

            {/* TABLA PRINCIPAL DE INVENTARIO */}
            <div className="table-section">
                <div className="table-responsive">
                    <table className="styled-table">
                        <thead>
                            <tr>
                                <th>ÍTEM / CÓDIGO</th>
                                <th style={{textAlign: 'center'}}>STOCK ACTUAL</th>
                                <th style={{textAlign: 'center'}}>STOCK MÍNIMO</th>
                                <th style={{textAlign: 'center'}}>ESTADO</th>
                                <th>ACCIONES</th>
                            </tr>
                        </thead>
                        <tbody>
                            {productosFiltrados.length === 0 ? (
                                <tr><td colSpan="5" style={{ textAlign: 'center', padding: '20px' }}>No se encontraron productos.</td></tr>
                            ) : (
                                productosFiltrados.map((prod) => (
                                    <tr key={prod.id}>
                                        <td>
                                            <div style={{fontWeight: 'bold', color: '#0f172a'}}>{prod.nombre}</div>
                                            <div style={{fontSize: '0.8rem', color: '#64748b'}}>{prod.codigo}</div>
                                        </td>
                                        <td style={{textAlign: 'center', fontWeight: 'bold', fontSize: '1.1rem'}}>{prod.stock_actual}</td>
                                        <td style={{textAlign: 'center', color: '#64748b'}}>{prod.stock_minimo}</td>
                                        <td style={{textAlign: 'center'}}>
                                            {obtenerEstadoUI(prod.stock_actual, prod.stock_minimo)}
                                        </td>
                                        <td>
                                            <div className="action-buttons">
                                                <button onClick={() => cargarParaEdicion(prod)} className="btn-icon btn-edit" title="Editar"><FaEdit /></button>
                                                <button onClick={() => eliminarProducto(prod.id)} className="btn-icon btn-delete" title="Eliminar"><FaTrashAlt /></button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* TABLA INFERIOR: MOVIMIENTOS RECIENTES (Igual a la imagen) */}
            <div className="table-section">
                <div className="table-header-dark">
                    <FaExclamationTriangle style={{ color: '#f59e0b' }} /> MOVIMIENTOS RECIENTES
                </div>
                <div className="table-responsive">
                    <table className="styled-table">
                        <thead>
                            <tr style={{backgroundColor: '#f8fafc', color: '#334155'}}>
                                <th>DATA (FECHA)</th>
                                <th>ÍTEM</th>
                                <th>MOVILIZADOR</th>
                            </tr>
                        </thead>
                        <tbody>
                            {movimientos.length === 0 ? (
                                <tr><td colSpan="3" style={{ textAlign: 'center', padding: '15px' }}>Aún no hay movimientos registrados.</td></tr>
                            ) : (
                                movimientos.slice(0, 5).map(mov => (
                                    <tr key={mov.id}>
                                        <td>{new Date(mov.fecha).toLocaleString()}</td>
                                        <td>{mov.tipo_movimiento}: {mov.cantidad} unidades</td>
                                        <td>{mov.usuario_nombre || 'Sistema'}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    );
};

export default Inventario;