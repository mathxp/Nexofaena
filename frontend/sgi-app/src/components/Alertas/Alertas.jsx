import { useState, useEffect } from 'react';
import { 
    FaExclamationCircle, FaCheckCircle, FaFileDownload, 
    FaCircle, FaExclamationTriangle, FaBell, FaBoxOpen 
} from 'react-icons/fa';
import api from '../../api';
import './Alertas.css';

const Alertas = () => {
    const [vistaActiva, setVistaActiva] = useState('STOCK'); // 'STOCK' o 'SISTEMA'
    
    // Datos
    const [inventario, setInventario] = useState([]);
    const [alertasSistema, setAlertasSistema] = useState([]);
    const [error, setError] = useState('');

    useEffect(() => {
        cargarDatos();
    }, []);

    const cargarDatos = async () => {
        try {
            const [resInv, resSys] = await Promise.all([
                api.get('/inventario/'),
                api.get('/alertas/').catch(() => ({ data: [] }))
            ]);
            setInventario(resInv.data);
            setAlertasSistema(resSys.data);
            setError('');
        } catch (err) {
            setError('Error al cargar la información del servidor.');
        }
    };

    const marcarComoLeida = async (id) => {
        try {
            await api.patch(`/alertas/${id}/`, { leida: true });
            cargarDatos();
        } catch (err) {
            setError('Error al actualizar el estado de la alerta.');
        }
    };

    // --- LÓGICA DE CLASIFICACIÓN DE STOCK ---
    // 1. Quiebre (Crítico): Stock actual menor al mínimo
    const stockCritico = inventario.filter(i => parseFloat(i.stock_actual) < parseFloat(i.stock_minimo));
    
    // 2. Bajo: Stock actual mayor o igual al mínimo, pero menor al mínimo + 20% (margen de seguridad)
    const stockBajo = inventario.filter(i => {
        const actual = parseFloat(i.stock_actual);
        const minimo = parseFloat(i.stock_minimo);
        return actual >= minimo && actual <= (minimo * 1.20);
    });

    // 3. Óptimo: Stock actual con holgura por encima del margen
    const stockOptimo = inventario.filter(i => parseFloat(i.stock_actual) > (parseFloat(i.stock_minimo) * 1.20));

    return (
        <div className="alertas-wrapper">
            <h1 className="page-title">
                <FaExclamationCircle /> Alertas de Stock
                <span className="title-sub">(PAÑOL / BODEGAS)</span>
            </h1>
            
            {error && <div className="error-msg"><FaExclamationTriangle /> {error}</div>}

            {/* SELECTOR DE VISTAS */}
            <div className="view-selector">
                <button className={`view-btn ${vistaActiva === 'STOCK' ? 'active' : ''}`} onClick={() => setVistaActiva('STOCK')}>
                    <FaBoxOpen /> Estado de Insumos
                </button>
                <button className={`view-btn ${vistaActiva === 'SISTEMA' ? 'active' : ''}`} onClick={() => setVistaActiva('SISTEMA')}>
                    <FaBell /> Notificaciones de Sistema
                </button>
            </div>

            {vistaActiva === 'STOCK' ? (
                <>
                    {/* PÍLDORAS SUPERIORES */}
                    <div className="status-pills">
                        <div className="pill pill-red">
                            <FaCircle style={{fontSize: '10px'}} /> CRÍTICO ({stockCritico.length})
                        </div>
                        <div className="pill pill-orange">
                            <FaCircle style={{fontSize: '10px'}} /> BAJO ({stockBajo.length})
                        </div>
                        <div className="pill pill-green">
                            <FaCircle style={{fontSize: '10px'}} /> OK ({stockOptimo.length})
                        </div>
                    </div>

                    <div className="cards-grid">
                        {/* TARJETA 1: QUIEBRE DE STOCK */}
                        <div className="stock-card">
                            <div className="card-header bg-red">
                                <FaCircle style={{fontSize: '12px'}} /> QUIEBRE DE STOCK (Urgente)
                            </div>
                            <div className="stock-list">
                                {stockCritico.length === 0 ? <div className="item-empty">No hay insumos en quiebre.</div> : 
                                    stockCritico.map(item => (
                                        <div key={item.id} className="stock-item">
                                            <FaExclamationTriangle className="item-icon icon-red" />
                                            <div className="item-details">
                                                <div className="item-name">{item.nombre}</div>
                                                <div className="item-stats">Stock Actual: {item.stock_actual} | Mínimo: {item.stock_minimo}</div>
                                            </div>
                                        </div>
                                    ))
                                }
                            </div>
                        </div>

                        {/* TARJETA 2: STOCK BAJO */}
                        <div className="stock-card">
                            <div className="card-header bg-orange">
                                <FaCircle style={{fontSize: '12px'}} /> STOCK BAJO (Programar)
                            </div>
                            <div className="stock-list">
                                {stockBajo.length === 0 ? <div className="item-empty">No hay insumos con stock bajo.</div> : 
                                    stockBajo.map(item => (
                                        <div key={item.id} className="stock-item">
                                            <FaExclamationTriangle className="item-icon icon-orange" />
                                            <div className="item-details">
                                                <div className="item-name">{item.nombre}</div>
                                                <div className="item-stats">Stock Actual: {item.stock_actual} | Mínimo: {item.stock_minimo}</div>
                                            </div>
                                        </div>
                                    ))
                                }
                            </div>
                        </div>

                        {/* TARJETA 3: STOCK ÓPTIMO */}
                        <div className="stock-card">
                            <div className="card-header bg-green">
                                <FaCircle style={{fontSize: '12px'}} /> STOCK ÓPTIMO (Sano)
                            </div>
                            <div className="stock-list">
                                {stockOptimo.length === 0 ? <div className="item-empty">No hay insumos en estado óptimo.</div> :
                                    stockOptimo.slice(0, 4).map(item => ( // Mostramos solo 4
                                        <div key={item.id} className="stock-item">
                                            <FaCheckCircle className="item-icon icon-green" />
                                            <div className="item-details">
                                                <div className="item-name">{item.nombre}</div>
                                                <div className="item-stats">Stock Actual: {item.stock_actual} | Mínimo: {item.stock_minimo}</div>
                                            </div>
                                        </div>
                                    ))
                                }
                                {stockOptimo.length > 4 && (
                                    <div className="item-empty" style={{color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)'}}>
                                        + {stockOptimo.length - 4} insumos en estado óptimo
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* BOTÓN EXPORTAR */}
                    <button className="btn-exportar" onClick={() => alert('Generando reporte...')}>
                        <FaFileDownload /> EXPORTAR REPORTE DE COMPRAS
                    </button>
                </>
            ) : (
                /* VISTA NOTIFICACIONES (SISTEMA) */
                <div className="system-alerts-container">
                    <table className="system-alerts-table">
                        <thead>
                            <tr>
                                <th>Fecha y Hora</th>
                                <th>Tipo de Alerta</th>
                                <th>Mensaje del Sistema</th>
                                <th>Acción</th>
                            </tr>
                        </thead>
                        <tbody>
                            {alertasSistema.length === 0 ? (
                                <tr><td colSpan="4" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>No hay notificaciones de sistema.</td></tr>
                            ) : (
                                alertasSistema.map((alerta) => (
                                    <tr key={alerta.id} className={alerta.leida ? 'row-read' : 'row-unread'}>
                                        <td style={{ color: alerta.leida ? '#94a3b8' : 'white' }}>
                                            {new Date(alerta.fecha_alerta).toLocaleString()}
                                        </td>
                                        <td>
                                            <span style={{ color: alerta.tipo_alerta === 'CRÍTICA' ? '#f87171' : '#fbbf24' }}>
                                                {alerta.tipo_alerta}
                                            </span>
                                        </td>
                                        <td>{alerta.mensaje}</td>
                                        <td>
                                            {!alerta.leida ? (
                                                <button onClick={() => marcarComoLeida(alerta.id)} className="btn-mark-read">
                                                    Marcar Leída
                                                </button>
                                            ) : (
                                                <span className="status-read"><FaCheckCircle /> Leída</span>
                                            )}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default Alertas;