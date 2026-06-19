import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
    FaUserFriends, FaBoxes, FaClock, FaTimesCircle, 
    FaTools, FaClipboardList, FaFilePdf, FaBook, 
    FaBell
} from 'react-icons/fa';
import api from '../../api';
import './Dashboard.css';

const Dashboard = () => {
    const navigate = useNavigate();
    const [inventario, setInventario] = useState([]);
    const [alertas, setAlertas] = useState([]);
    const [trabajadores, setTrabajadores] = useState([]);

    useEffect(() => {
        cargarDatos();
    }, []);

    const cargarDatos = async () => {
        try {
            const [resInv, resAlertas, resTrab] = await Promise.all([
                api.get('/inventario/'),
                api.get('/alertas/'),
                api.get('/trabajadores/')
            ]);
            setInventario(resInv.data);
            setAlertas(resAlertas.data);
            setTrabajadores(resTrab.data);
        } catch (err) {
            console.error(err);
            if (err.response && err.response.status === 401) {
                localStorage.removeItem('access_token');
                navigate('/');
            }
        }
    };

    const totalTrabajadores = trabajadores.length || 1;
    const stockTotal = inventario.reduce((acc, item) => acc + parseFloat(item.stock_actual), 0);
    const alertasActivas = alertas.filter(a => !a.leida);
    const itemsCriticos = inventario.filter(item => parseFloat(item.stock_actual) <= parseFloat(item.stock_minimo));
    const cantidadCriticos = itemsCriticos.length;
    const elementosRechazados = 5; 

    return (
        <div className="dashboard-wrapper">
            
            {/* CABECERA COMPACTA */}
            <div className="header-info">
                <div className="header-titles">
                    <h1>DASHBOARD PRINCIPAL</h1>
                    <p>¡Hola, Supervisor! Resumen de la operación actual.</p>
                </div>
                <div className="status-badge">
                    <span className="pulse-dot"></span> SISTEMA CONECTADO
                </div>
            </div>

            {/* KPIs GRID (Ahora son elegantes y delgados) */}
            <div className="kpi-grid">
                <div className="kpi-card kpi-blue">
                    <div className="kpi-icon-box"><FaUserFriends /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Total Trabajadores</p>
                        <h3 className="kpi-value">{totalTrabajadores}</h3>
                    </div>
                </div>
                <div className="kpi-card kpi-blue">
                    <div className="kpi-icon-box"><FaBoxes /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Stock Disponible</p>
                        <h3 className="kpi-value">{stockTotal.toLocaleString() || 80}</h3>
                    </div>
                </div>
                <div className="kpi-card kpi-orange">
                    <div className="kpi-icon-box"><FaClock /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Próximos a Vencer</p>
                        <h3 className="kpi-value">{cantidadCriticos}</h3>
                    </div>
                </div>
                <div className="kpi-card kpi-red">
                    <div className="kpi-icon-box"><FaTimesCircle /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Elementos Rechazados</p>
                        <h3 className="kpi-value">{elementosRechazados}</h3>
                    </div>
                </div>
            </div>

            {/* ALERTAS ESTILIZADAS */}
            <div className="alert-section">
                <div className="alert-header">
                    <FaBell style={{ color: '#fcd34d' }} /> ALERTAS DEL SISTEMA
                </div>
                
                {alertasActivas.length === 0 ? (
                    <p style={{color: '#94a3b8', margin: 0, fontSize: '0.9rem'}}>No hay alertas pendientes. Todo en orden.</p>
                ) : (
                    alertasActivas.slice(0, 3).map(alerta => {
                        const esCritica = alerta.tipo_alerta === 'CRÍTICA';
                        return (
                            <div key={alerta.id} className={`alert-item ${esCritica ? 'urgente' : 'aviso'}`}>
                                <span className={esCritica ? 'badge-urgente' : 'badge-aviso'}>
                                    {alerta.tipo_alerta || 'AVISO'}
                                </span> 
                                <span>{alerta.mensaje}</span>
                            </div>
                        );
                    })
                )}
                
                <button onClick={() => navigate('/alertas')} className="btn-ver-todas">
                    Ver historial completo &rarr;
                </button>
            </div>

            {/* ACCESOS RÁPIDOS COMPACTOS */}
            <h3 className="quick-access-header">🚀 Módulos Operativos</h3>
            <div className="quick-access-grid">
                <button onClick={() => navigate('/entregas')} className="qa-btn">
                    <div className="qa-icon-wrapper"><FaTools /></div>
                    <span>Entregas Pañol</span>
                </button>
                <button onClick={() => navigate('/epps')} className="qa-btn">
                    <div className="qa-icon-wrapper"><FaClipboardList /></div>
                    <span>Catálogo EPP</span>
                </button>
                <button onClick={() => navigate('/reportes')} className="qa-btn">
                    <div className="qa-icon-wrapper"><FaFilePdf /></div>
                    <span>Reportes y PDF</span>
                </button>
                <button onClick={() => navigate('/inventario')} className="qa-btn">
                    <div className="qa-icon-wrapper"><FaBook /></div>
                    <span>Inventario Total</span>
                </button>
            </div>

        </div>
    );
};

export default Dashboard;