import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
    FaTachometerAlt, FaChartPie, FaTools, FaHardHat, 
    FaBoxes, FaBuilding, FaExchangeAlt, FaUserFriends, 
    FaBell, FaFileAlt, FaSignOutAlt, FaUserCircle, 
    FaBars, FaTimes 
} from 'react-icons/fa';
import './Sidebar.css';

const Sidebar = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const [isMobileOpen, setIsMobileOpen] = useState(false);

    const handleLogout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        navigate('/');
    };

    const navItems = [
        { path: '/dashboard', icon: <FaTachometerAlt />, label: 'Dashboard' },
        { path: '/dashboard-gerencial', icon: <FaChartPie />, label: 'Gerencial' },
        { path: '/entregas', icon: <FaTools />, label: 'Entregas Pañol' },
        { path: '/epps', icon: <FaHardHat />, label: 'Catálogo EPP' },
        { path: '/inventario', icon: <FaBoxes />, label: 'Inventario' },
        { path: '/bodegas', icon: <FaBuilding />, label: 'Bodegas' },
        { path: '/movimientos', icon: <FaExchangeAlt />, label: 'Movimientos' },
        { path: '/trabajadores', icon: <FaUserFriends />, label: 'Personal' },
        { path: '/alertas', icon: <FaBell />, label: 'Alertas' },
        { path: '/reportes', icon: <FaFileAlt />, label: 'Reportes' },
    ];

    return (
        <>
            <div className="mobile-header">
                <div className="mobile-brand">
                    <FaBuilding style={{color: '#ea580c'}} /> NEXO<span>FAENA</span>
                </div>
                <button className="mobile-toggle" onClick={() => setIsMobileOpen(!isMobileOpen)}>
                    {isMobileOpen ? <FaTimes /> : <FaBars />}
                </button>
            </div>

            {isMobileOpen && <div className="sidebar-overlay" onClick={() => setIsMobileOpen(false)}></div>}

            <aside className={`sidebar ${isMobileOpen ? 'open' : ''}`}>
                <div className="sidebar-brand">
                    <FaBuilding className="brand-icon" />
                    <div className="brand-text">NEXO<span>FAENA</span></div>
                </div>

                <div className="sidebar-menu">
                    <div className="menu-label">Menú Principal</div>
                    
                    {navItems.map((item) => (
                        <button 
                            key={item.path}
                            onClick={() => { navigate(item.path); setIsMobileOpen(false); }}
                            className={`menu-item ${location.pathname === item.path ? 'active' : ''}`}
                        >
                            <span className="menu-icon">{item.icon}</span>
                            <span className="menu-text">{item.label}</span>
                        </button>
                    ))}
                </div>

                <div className="sidebar-footer">
                    <div className="user-info">
                        <FaUserCircle className="user-icon" />
                        <div>
                            <div className="user-name">Supervisor</div>
                            <div className="user-role">Conectado</div>
                        </div>
                    </div>
                    <button onClick={handleLogout} className="btn-logout">
                        <FaSignOutAlt /> Cerrar Sesión
                    </button>
                </div>
            </aside>
        </>
    );
};

export default Sidebar;