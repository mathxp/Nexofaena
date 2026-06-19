import { BrowserRouter as Router, Routes, Route, Outlet } from 'react-router-dom';

// Importaciones actualizadas a la nueva estructura de carpetas
import Login from './components/Login/Login';
import Dashboard from './components/Dashboard/Dashboard';
import DashboardGerencial from './components/DashboardGerencial/DashboardGerencial';
import Trabajadores from './components/Trabajadores/Trabajadores';
import Bodegas from './components/Bodegas/Bodegas';
import Inventario from './components/Inventario/Inventario';
import Movimientos from './components/Movimientos/Movimientos';
import Epp from './components/Epp/Epp';
import Entregas from './components/Entregas/Entregas';
import Alertas from './components/Alertas/Alertas';
import Reportes from './components/Reportes/Reportes';
import Sidebar from './components/Sidebar/Sidebar'; // SOLO IMPORTAMOS EL SIDEBAR

// Plantilla Maestra: Solo Sidebar a la izquierda y el contenido a la derecha
const LayoutConSidebar = () => {
    return (
        <div className="app-layout">
            <Sidebar />
            <main className="main-content">
                <Outlet /> 
            </main>
        </div>
    );
};

function App() {
    return (
        <Router>
            <Routes>
                {/* RUTA PÚBLICA */}
                <Route path="/" element={<Login />} />

                {/* RUTAS PRIVADAS (Usan la plantilla con el Sidebar) */}
                <Route element={<LayoutConSidebar />}>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/dashboard-gerencial" element={<DashboardGerencial />} />
                    <Route path="/trabajadores" element={<Trabajadores />} />
                    <Route path="/bodegas" element={<Bodegas />} />
                    <Route path="/inventario" element={<Inventario />} />
                    <Route path="/movimientos" element={<Movimientos />} />
                    <Route path="/epps" element={<Epp />} />
                    <Route path="/entregas" element={<Entregas />} />
                    <Route path="/alertas" element={<Alertas />} />
                    <Route path="/reportes" element={<Reportes />} />
                </Route>
            </Routes>
        </Router>
    );
}

export default App;