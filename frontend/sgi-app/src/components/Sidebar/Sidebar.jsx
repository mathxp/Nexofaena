import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  FaTachometerAlt, FaChartPie, FaTools, FaBoxes,
  FaBuilding, FaExchangeAlt, FaUserFriends, FaBell,
  FaFileAlt, FaSignOutAlt, FaUserCircle, FaBars, FaTimes
} from 'react-icons/fa';

import api from '../../api';
import './Sidebar.css';

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [alertasNoLeidas, setAlertasNoLeidas] = useState(0);

  const role = localStorage.getItem('user_role') || '';
  const username = localStorage.getItem('username') || 'Usuario';

  useEffect(() => {
    cargarAlertas();

    const interval = setInterval(() => {
      cargarAlertas();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const cargarAlertas = async () => {
    try {
      const response = await api.get('/alertas/');
      const data = Array.isArray(response.data) ? response.data : [];
      setAlertasNoLeidas(data.filter((a) => !a.leida).length);
    } catch {
      setAlertasNoLeidas(0);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('username');
    navigate('/');
  };

  const navItems = [
    {
      path: '/dashboard',
      icon: <FaTachometerAlt />,
      label: 'Dashboard',
      roles: ['Administrador', 'Supervisor', 'Bodeguero', 'Operador'],
    },
    {
      path: '/dashboard-gerencial',
      icon: <FaChartPie />,
      label: 'Gerencial',
      roles: ['Administrador', 'Supervisor'],
    },
    {
      path: '/entregas',
      icon: <FaTools />,
      label: 'Entregas Pañol',
      roles: ['Administrador', 'Bodeguero'],
    },
    {
      path: '/inventario',
      icon: <FaBoxes />,
      label: 'Inventario',
      roles: ['Administrador', 'Supervisor', 'Bodeguero'],
    },
    {
      path: '/bodegas',
      icon: <FaBuilding />,
      label: 'Bodegas',
      roles: ['Administrador', 'Supervisor', 'Bodeguero'],
    },
    {
      path: '/movimientos',
      icon: <FaExchangeAlt />,
      label: 'Movimientos',
      roles: ['Administrador', 'Supervisor', 'Bodeguero'],
    },
    {
      path: '/trabajadores',
      icon: <FaUserFriends />,
      label: 'Personal',
      roles: ['Administrador'],
    },
    {
      path: '/alertas',
      icon: <FaBell />,
      label: alertasNoLeidas > 0 ? `Alertas (${alertasNoLeidas})` : 'Alertas',
      roles: ['Administrador', 'Supervisor', 'Bodeguero'],
    },
    {
      path: '/conteo-ciclico',
      icon: <FaBoxes />,
      label: 'Conteo Cíclico',
      roles: ['Administrador', 'Supervisor', 'Bodeguero'],
    },
    {
      path: '/auditorias-inventario',
      icon: <FaFileAlt />,
      label: 'Auditorías',
      roles: ['Administrador', 'Supervisor', 'Bodeguero'],
    },
    {
      path: '/reportes',
      icon: <FaFileAlt />,
      label: 'Reportes',
      roles: ['Administrador', 'Supervisor'],
    },
  ];

  const navItemsPermitidos = navItems.filter((item) =>
    item.roles.includes(role)
  );

  return (
    <>
      <div className="mobile-header">
        <div className="mobile-brand">
          <FaBuilding style={{ color: '#ea580c' }} /> NEXO<span>FAENA</span>
        </div>

        <button className="mobile-toggle" onClick={() => setIsMobileOpen(!isMobileOpen)}>
          {isMobileOpen ? <FaTimes /> : <FaBars />}
        </button>
      </div>

      {isMobileOpen && (
        <div className="sidebar-overlay" onClick={() => setIsMobileOpen(false)}></div>
      )}

      <aside className={`sidebar ${isMobileOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <FaBuilding className="brand-icon" />
          <div className="brand-text">NEXO<span>FAENA</span></div>
        </div>

        <div className="sidebar-menu">
          <div className="menu-label">Menú Principal</div>

          {navItemsPermitidos.map((item) => (
            <button
              key={item.path}
              onClick={() => {
                navigate(item.path);
                setIsMobileOpen(false);
              }}
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
              <div className="user-name">{username}</div>
              <div className="user-role">{role || 'Sin rol'}</div>
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