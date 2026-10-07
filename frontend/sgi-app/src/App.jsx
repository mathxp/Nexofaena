import { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Outlet } from 'react-router-dom';

import Sidebar from './components/Sidebar/Sidebar';
import ProtectedRoute from './components/ProtectedRoute';
import RoleProtectedRoute from './components/RoleProtectedRoute';
import lazyConRecarga from './utils/lazyConRecarga';

// Cada ruta se carga bajo demanda (code-splitting): el bundle inicial ya no
// arrastra ExcelJS/jsPDF/Chart.js/html2canvas de módulos que el usuario puede
// no visitar nunca en la sesión. Sidebar/ProtectedRoute quedan eager porque
// se necesitan de inmediato en cualquier ruta privada.
const Login = lazyConRecarga(() => import('./components/Login/Login'));
const Registro = lazyConRecarga(() => import('./components/Registro/Registro'));
const OlvidePassword = lazyConRecarga(() => import('./components/OlvidePassword/OlvidePassword'));
const ResetPassword = lazyConRecarga(() => import('./components/ResetPassword/ResetPassword'));
const Dashboard = lazyConRecarga(() => import('./components/Dashboard/Dashboard'));
const DashboardGerencial = lazyConRecarga(() => import('./components/DashboardGerencial/DashboardGerencial'));
const Trabajadores = lazyConRecarga(() => import('./components/Trabajadores/Trabajadores'));
const Bodegas = lazyConRecarga(() => import('./components/Bodegas/Bodegas'));
const Inventario = lazyConRecarga(() => import('./components/Inventario/Inventario'));
const Movimientos = lazyConRecarga(() => import('./components/Movimientos/Movimientos'));
const Entregas = lazyConRecarga(() => import('./components/Entregas/Entregas'));
const Devoluciones = lazyConRecarga(() => import('./components/Devoluciones/Devoluciones'));
const Alertas = lazyConRecarga(() => import('./components/Alertas/Alertas'));
const Reportes = lazyConRecarga(() => import('./components/Reportes/Reportes'));
const AuditoriasInventario = lazyConRecarga(() => import('./components/AuditoriasInventario/AuditoriasInventario'));
const Kiosco = lazyConRecarga(() => import('./components/Kiosco/Kiosco'));

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
