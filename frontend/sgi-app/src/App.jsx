import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Outlet } from 'react-router-dom';

import Sidebar from './components/Sidebar/Sidebar';
import ProtectedRoute from './components/ProtectedRoute';
import RoleProtectedRoute from './components/RoleProtectedRoute';

// Cada ruta se carga bajo demanda (code-splitting): el bundle inicial ya no
// arrastra ExcelJS/jsPDF/Chart.js/html2canvas de módulos que el usuario puede
// no visitar nunca en la sesión. Sidebar/ProtectedRoute quedan eager porque
// se necesitan de inmediato en cualquier ruta privada.
const Login = lazy(() => import('./components/Login/Login'));
const Registro = lazy(() => import('./components/Registro/Registro'));
const OlvidePassword = lazy(() => import('./components/OlvidePassword/OlvidePassword'));
const ResetPassword = lazy(() => import('./components/ResetPassword/ResetPassword'));
const Dashboard = lazy(() => import('./components/Dashboard/Dashboard'));
const DashboardGerencial = lazy(() => import('./components/DashboardGerencial/DashboardGerencial'));
const Trabajadores = lazy(() => import('./components/Trabajadores/Trabajadores'));
const Bodegas = lazy(() => import('./components/Bodegas/Bodegas'));
const Inventario = lazy(() => import('./components/Inventario/Inventario'));
const Movimientos = lazy(() => import('./components/Movimientos/Movimientos'));
const Entregas = lazy(() => import('./components/Entregas/Entregas'));
const Devoluciones = lazy(() => import('./components/Devoluciones/Devoluciones'));
const Alertas = lazy(() => import('./components/Alertas/Alertas'));
const Reportes = lazy(() => import('./components/Reportes/Reportes'));
const AuditoriasInventario = lazy(() => import('./components/AuditoriasInventario/AuditoriasInventario'));
const Kiosco = lazy(() => import('./components/Kiosco/Kiosco'));

const PageLoader = () => (
  <div
    style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#001529',
      color: '#94a3b8',
      fontFamily: "'Inter', sans-serif",
      fontSize: '0.95rem',
      fontWeight: 600,
    }}
  >
    Cargando...
  </div>
);

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
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Rutas públicas */}
          <Route path="/" element={<Login />} />
          <Route path="/register" element={<Registro />} />
          <Route path="/forgot-password" element={<OlvidePassword />} />
          <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />

          {/* Rutas privadas */}
          <Route element={<ProtectedRoute />}>
            {/* Kiosco de autoservicio: pantalla completa, sin Sidebar — el
                trabajador solo ve esto, nunca el resto del sistema. El
                dispositivo (RPi4/tablet) queda logueado con una cuenta de
                staff (Administrador/Bodeguero) una sola vez. */}
            <Route
              path="/kiosco"
              element={
                <RoleProtectedRoute allowedRoles={['Administrador', 'Bodeguero']}>
                  <Kiosco />
                </RoleProtectedRoute>
              }
            />

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
                path="/devoluciones"
                element={
                  <RoleProtectedRoute allowedRoles={['Administrador', 'Bodeguero']}>
                    <Devoluciones />
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
      </Suspense>
    </Router>
  );
}

export default App;
