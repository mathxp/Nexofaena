import { useState, useEffect } from 'react';
import { FaExchangeAlt, FaPlus, FaHistory, FaExclamationTriangle, FaCheckCircle } from 'react-icons/fa';
import api from '../../api';
import './Movimientos.css';

const Movimientos = () => {
    const [movimientos, setMovimientos] = useState([]);
    const [productos, setProductos] = useState([]);
    const [bodegas, setBodegas] = useState([]);
    const [usuarios, setUsuarios] = useState([]); 
    
    const [error, setError] = useState('');
    const [exito, setExito] = useState(''); // Estado para mensaje de éxito
    
    const [formData, setFormData] = useState({
        usuario: '',
        bodega: '',
        inventario: '',
        tipo_movimiento: 'INGRESO',
        cantidad: '',
        observacion: ''
    });

    useEffect(() => {
        cargarDatos();
    }, []);

    const cargarDatos = async () => {
        try {
            const [resMovs, resProds, resBodegas, resUsuarios] = await Promise.all([
                api.get('/movimientos/'),
                api.get('/inventario/'),
                api.get('/bodegas/'),
                api.get('/usuarios/')
            ]);
            setMovimientos(resMovs.data);
            setProductos(resProds.data);
            setBodegas(resBodegas.data);
            setUsuarios(resUsuarios.data);
            setError('');
        } catch (err) {
            console.error(err);
            setError('Error al cargar la información del servidor.');
        }
    };

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setExito('');

        try {
            // 1. Guardamos el registro del movimiento
            await api.post('/movimientos/', formData);

            // 2. Lógica para actualizar el stock del producto en la base de datos
            const productoSeleccionado = productos.find(p => p.id === parseInt(formData.inventario));
            let nuevoStock = parseFloat(productoSeleccionado.stock_actual);
            const cantidadMovimiento = parseFloat(formData.cantidad);

            if (formData.tipo_movimiento === 'INGRESO') {
                nuevoStock += cantidadMovimiento;
            } else if (formData.tipo_movimiento === 'SALIDA') {
                nuevoStock -= cantidadMovimiento;
            } else if (formData.tipo_movimiento === 'AJUSTE') {
                nuevoStock = cantidadMovimiento;
            }

            // Enviamos la actualización (PATCH) del producto
            await api.patch(`/inventario/${productoSeleccionado.id}/`, { stock_actual: nuevoStock });

            // 3. Limpiamos y recargamos
            setFormData({ ...formData, cantidad: '', observacion: '' }); 
            cargarDatos();
            setExito('¡Movimiento de inventario registrado correctamente!');
            
            // Ocultar éxito después de 3 segundos
            setTimeout(() => setExito(''), 3000);
        } catch (err) {
            console.error(err);
            setError('Error al registrar el movimiento. Verifica los campos requeridos.');
        }
    };

    const getNombreProducto = (id) => {
        const prod = productos.find(p => p.id === id);
        return prod ? prod.nombre : 'Desconocido';
    };

    // Helper para renderizar los badges de estado
    const renderBadge = (tipo) => {
        if (tipo === 'INGRESO') return <span className="badge-mov badge-ingreso">Ingreso</span>;
        if (tipo === 'SALIDA') return <span className="badge-mov badge-salida">Salida</span>;
        return <span className="badge-mov badge-ajuste">Ajuste</span>;
    };

    return (
        <div className="movimientos-wrapper">
            <h1 className="page-title"><FaExchangeAlt /> Movimientos de Inventario</h1>
            
            {error && <div className="alert-msg alert-error"><FaExclamationTriangle /> {error}</div>}
            {exito && <div className="alert-msg alert-success"><FaCheckCircle /> {exito}</div>}

            {/* FORMULARIO */}
            <div className="form-container">
                <div className="form-header">
                    <FaPlus style={{color: '#ea580c'}} /> Registrar Nueva Entrada / Salida
                </div>
                
                <form onSubmit={handleSubmit} className="form-grid">
                    
                    <div className="input-group">
                        <label className="input-label">Usuario Responsable</label>
                        <select className="custom-select" name="usuario" value={formData.usuario} onChange={handleChange} required>
                            <option value="">-- Seleccione Usuario --</option>
                            {usuarios.map(u => <option key={u.id} value={u.id}>{u.username} ({u.rut || 'Sin RUT'})</option>)}
                        </select>
                    </div>

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
                    </div>

                    <div className="input-group">
                        <label className="input-label">Cantidad a mover</label>
                        <input className="form-input" type="number" step="0.01" name="cantidad" placeholder="Ej: 10" value={formData.cantidad} onChange={handleChange} required />
                    </div>
                    
                    <div className="input-group">
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
                    <FaHistory style={{color: '#94a3b8'}} /> Historial de Movimientos
                </div>
                <div className="table-responsive">
                    <table className="styled-table">
                        <thead>
                            <tr>
                                <th>Tipo</th>
                                <th>Producto</th>
                                <th>Cantidad</th>
                                <th>Fecha y Hora</th>
                            </tr>
                        </thead>
                        <tbody>
                            {movimientos.length === 0 ? (
                                <tr>
                                    <td colSpan="4" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                                        No hay movimientos registrados en el sistema.
                                    </td>
                                </tr>
                            ) : (
                                [...movimientos].reverse().map((mov) => (
                                    <tr key={mov.id}>
                                        <td>{renderBadge(mov.tipo_movimiento)}</td>
                                        <td style={{ fontWeight: '700' }}>{getNombreProducto(mov.inventario)}</td>
                                        <td style={{ fontWeight: '900', fontSize: '1.1rem' }}>{mov.cantidad}</td>
                                        <td style={{ color: '#94a3b8' }}>{new Date(mov.fecha).toLocaleString()}</td>
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

export default Movimientos;