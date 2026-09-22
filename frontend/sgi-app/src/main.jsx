import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import './index.css'
import App from './App.jsx'

// Sin VITE_SENTRY_DSN (dev local, o si nunca se configura en el hosting del
// frontend) esto no hace nada: no manda eventos ni cambia el comportamiento.
const sentryDsn = import.meta.env.VITE_SENTRY_DSN
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.PROD ? 'production' : 'development',
    // 10% de las interacciones con traza de performance: suficiente para
    // ver cuellos de botella sin agotar la cuota gratuita.
    tracesSampleRate: 0.1,
  })
}

// El kiosco corre sin nadie mirando durante todo un turno: si un componente
// revienta al renderizar, mejor un mensaje que decirle al trabajador que
// recargue, que una pantalla en blanco silenciosa.
const ErrorFallback = () => (
  <div
    style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.75rem',
      background: '#001529',
      color: '#94a3b8',
      fontFamily: "'Inter', sans-serif",
      textAlign: 'center',
      padding: '1rem',
    }}
  >
    <p style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>
      Ocurrió un error inesperado.
    </p>
    <button
      onClick={() => window.location.reload()}
      style={{
        padding: '0.6rem 1.5rem',
        borderRadius: '8px',
        border: 'none',
        background: '#f97316',
        color: '#001529',
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      Recargar página
    </button>
  </div>
)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<ErrorFallback />}>
      <App />
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
