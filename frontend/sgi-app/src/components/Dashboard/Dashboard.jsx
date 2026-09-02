import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    FaUserFriends, FaBoxes, FaExclamationTriangle, FaBell,
    FaTools, FaFilePdf, FaBook, FaSyncAlt,
} from 'react-icons/fa';
import api from '../../api';
import './Dashboard.css';

const TIPOS_URGENTES = ['STOCK_CRITICO', 'VENCIMIENTO', 'CIERRE_TURNO'];
const TIPOS_AVISO = ['STOCK_BAJO', 'ANOMALIA_CONSUMO', 'MANTENIMIENTO'];

const quickAccessItems = [
    { path: '/entregas', icon: <FaTools />, label: 'Entregas Pañol', roles: ['Administrador', 'Bodeguero'] },
    { path: '/devoluciones', icon: <FaSyncAlt />, label: 'Devoluciones', roles: ['Administrador', 'Bodeguero'] },
    { path: '/inventario', icon: <FaBook />, label: 'Inventario Total', roles: ['Administrador', 'Supervisor', 'Bodeguero'] },
    { path: '/reportes', icon: <FaFilePdf />, label: 'Reportes y PDF', roles: ['Administrador', 'Supervisor'] },
];

const Dashboard = () => {
    const navigate = useNavigate();
    const [inventario, setInventario] = useState([]);
    const [alertas, setAlertas] = useState([]);
    const [trabajadores, setTrabajadores] = useState([]);
    const [radiosPendientes, setRadiosPendientes] = useState([]);
    const [cargando, setCargando] = useState(true);

    const role = localStorage.getItem('user_role') || '';

    useEffect(() => {
        cargarDatos();
    }, []);

    const cargarDatos = async () => {
        try {
            setCargando(true);

            const [resInv, resAlertas, resTrab, resRadios] = await Promise.all([
                api.get('/inventario/'),
                api.get('/alertas/'),
                api.get('/trabajadores/'),
                api.get('/detalles-entrega-epp/?pendientes=true').catch(() => ({ data: [] })),
            ]);

            setInventario(resInv.data);
            setAlertas(resAlertas.data);
            setTrabajadores(resTrab.data);
            setRadiosPendientes(resRadios.data);
        } catch (err) {
            console.error(err);
            if (err.response && err.response.status === 401) {
                localStorage.removeItem('access_token');
                navigate('/');
            }
        } finally {
            setCargando(false);
        }
    };

    const trabajadoresActivos = trabajadores.filter((t) => t.activo).length;
    const stockTotal = inventario.reduce((acc, item) => acc + Number(item.stock_actual || 0), 0);
    const productosCriticos = inventario.filter((item) => item.necesita_reposicion).length;
    const alertasActivas = alertas.filter((a) => !a.leida);

    const badgeParaAlerta = (tipo) => {
        if (TIPOS_URGENTES.includes(tipo)) return 'urgente';
        if (TIPOS_AVISO.includes(tipo)) return 'aviso';
        return 'info';
    };

    const quickAccessPermitidos = quickAccessItems.filter((item) => item.roles.includes(role));

    return (
        <div className="dashboard-wrapper">

            {/* CABECERA COMPACTA */}
            <div className="header-info">
                <div className="header-titles">
                    <h1>DASHBOARD PRINCIPAL</h1>
                    <p>Resumen de la operación actual.</p>
                </div>
                <div className="status-badge">
                    <span className="pulse-dot"></span> {cargando ? 'ACTUALIZANDO...' : 'SISTEMA CONECTADO'}
                </div>
            </div>

            {/* KPIs GRID */}
            <div className="kpi-grid">
                <div className="kpi-card kpi-blue">
                    <div className="kpi-icon-box"><FaUserFriends /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Trabajadores Activos</p>
                        <h3 className="kpi-value">{trabajadoresActivos}</h3>
                    </div>
                </div>

                <div className="kpi-card kpi-orange">
                    <div className="kpi-icon-box"><FaBoxes /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Stock Disponible</p>
                        <h3 className="kpi-value">{stockTotal.toLocaleString()}</h3>
                    </div>
                </div>

                <div className="kpi-card kpi-red">
                    <div className="kpi-icon-box"><FaExclamationTriangle /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Stock Crítico</p>
                        <h3 className="kpi-value">{productosCriticos}</h3>
                    </div>
                </div>

                <div className="kpi-card kpi-red">
                    <div className="kpi-icon-box"><FaBell /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Alertas Activas</p>
                        <h3 className="kpi-value">{alertasActivas.length}</h3>
                    </div>
                </div>

                <div className="kpi-card kpi-blue">
                    <div className="kpi-icon-box"><FaSyncAlt /></div>
                    <div className="kpi-info">
                        <p className="kpi-label">Radios por Devolver</p>
                        <h3 className="kpi-value">{radiosPendientes.length}</h3>
                    </div>
                </div>
            </div>

            {/* ALERTAS ESTILIZADAS */}
            <div className="alert-section">
                <div className="alert-header">
                    <FaBell style={{ color: '#fcd34d' }} /> ALERTAS DEL SISTEMA
                </div>

                {alertasActivas.length === 0 ? (
                    <p className="alert-empty">No hay alertas pendientes. Todo en orden.</p>
                ) : (
                    alertasActivas.slice(0, 4).map((alerta) => {
                        const nivel = badgeParaAlerta(alerta.tipo_alerta);
                        return (
                            <div key={alerta.id} className={`alert-item ${nivel}`}>
                                <span className={`badge-${nivel}`}>
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
            <h3 className="quick-access-header">Módulos Operativos</h3>

            {quickAccessPermitidos.length === 0 ? (
                <p className="alert-empty">No tienes accesos rápidos asignados para tu rol.</p>
            ) : (
                <div className="quick-access-grid">
                    {quickAccessPermitidos.map((item) => (
                        <button key={item.path} onClick={() => navigate(item.path)} className="qa-btn">
                            <div className="qa-icon-wrapper">{item.icon}</div>
                            <span>{item.label}</span>
                        </button>
                    ))}
                </div>
            )}

        </div>
    );
};

export default Dashboard;
