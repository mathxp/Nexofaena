import { BrowserRouter as Router, Routes, Route, Outlet } from 'react-router-dom';

import Login from './components/Login/Login';
import Registro from './components/Registro/Registro';
import OlvidePassword from './components/OlvidePassword/OlvidePassword';
import ResetPassword from './components/ResetPassword/ResetPassword';
import ConteoCiclico from './components/ConteoCiclico/ConteoCiclico';
import Dashboard from './components/Dashboard/Dashboard';
import DashboardGerencial from './components/DashboardGerencial/DashboardGerencial';
import Trabajadores from './components/Trabajadores/Trabajadores';
import Bodegas from './components/Bodegas/Bodegas';
import Inventario from './components/Inventario/Inventario';
import Movimientos from './components/Movimientos/Movimientos';
import Entregas from './components/Entregas/Entregas';
import Alertas from './components/Alertas/Alertas';
import Reportes from './components/Reportes/Reportes';
import AuditoriasInventario from './components/AuditoriasInventario/AuditoriasInventario';
import Sidebar from './components/Sidebar/Sidebar';
import ProtectedRoute from './components/ProtectedRoute';
import RoleProtectedRoute from './components/RoleProtectedRoute';

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
        {/* Rutas públicas */}
        <Route path="/" element={<Login />} />
        <Route path="/register" element={<Registro />} />
        <Route path="/forgot-password" element={<OlvidePassword />} />
        <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />

        {/* Rutas privadas */}
        <Route element={<ProtectedRoute />}>
          <Route element={<LayoutConSidebar />}>
            <Route
              path="/dashboard"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor', 'Bodeguero', 'Operador']}>
                  <Dashboard />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/dashboard-gerencial"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor']}>
                  <DashboardGerencial />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/trabajadores"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador']}>
                  <Trabajadores />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/bodegas"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor', 'Bodeguero']}>
                  <Bodegas />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/inventario"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor', 'Bodeguero']}>
                  <Inventario />
                </RoleProtectedRoute>
              }
            />
            <Route
              path="/auditorias-inventario"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor', 'Bodeguero']}>
                  <AuditoriasInventario />
                </RoleProtectedRoute>
              }
            />
            <Route
              path="/movimientos"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor', 'Bodeguero']}>
                  <Movimientos />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/entregas"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Bodeguero']}>
                  <Entregas />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/alertas"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor', 'Bodeguero']}>
                  <Alertas />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/conteo-ciclico"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor', 'Bodeguero']}>
                  <ConteoCiclico />
                </RoleProtectedRoute>
              }
            />

            <Route
              path="/reportes"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Supervisor']}>
                  <Reportes />
                </RoleProtectedRoute>
              }
            />
          </Route>
        </Route>
      </Routes>
    </Router>
  );
}

export default App;