import { useState, useEffect } from 'react';
import {
  FaBolt,
  FaMapMarkerAlt,
  FaCheckCircle,
  FaExclamationTriangle,
  FaChartBar,
  FaWifi,
  FaSignal,
} from 'react-icons/fa';

import api from '../../api';
import './DespachoRapido.css';

const DespachoRapido = () => {
  const [bodegas, setBodegas] = useState([]);
  const [bodegaSeleccionada, setBodegaSeleccionada] = useState('');
  const [productos, setProductos] = useState([]);
  const [estadisticas, setEstadisticas] = useState([]);

  const [error, setError] = useState('');
  const [exito, setExito] = useState('');
  const [despachando, setDespachando] = useState(null);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    cargarBodegas();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (bodegaSeleccionada) {
      cargarDatos();
    } else {
      setProductos([]);
      setEstadisticas([]);
    }
  }, [bodegaSeleccionada]);

  const cargarBodegas = async () => {
    if (!navigator.onLine) {
      setIsOffline(true);
      return;
    }

    try {
      const res = await api.get('/bodegas/');
      setBodegas(res.data);
      setIsOffline(false);
    } catch (err) {
      console.error(err);
      setError('Error al cargar bodegas del servidor.');
    }
  };

  const cargarDatos = async () => {
    if (!navigator.onLine) {
      setIsOffline(true);
      setError('El despacho rápido requiere conexión.');
      return;
    }

    try {
      setError('');

      const [resInv, resStats] = await Promise.all([
        api.get(`/inventario/?bodega=${bodegaSeleccionada}`),
        api.get(`/despacho-rapido/stats/?bodega=${bodegaSeleccionada}`),
      ]);

      setProductos(resInv.data.filter((p) => p.es_despacho_rapido));
      setEstadisticas(resStats.data);
      setIsOffline(false);
    } catch (err) {
      console.error(err);

      if (!navigator.onLine) {
        setIsOffline(true);
        setError('El despacho rápido requiere conexión.');
      } else {
        setError('Error al cargar los productos de despacho rápido.');
      }
    }
  };

  const despachar = async (producto, cantidad) => {
    if (!navigator.onLine) {
      setError('⚠️ No es posible despachar sin conexión.');
      return;
    }

    setError('');
    setExito('');
    setDespachando(producto.id);

    try {
      await api.post('/despacho-rapido/', {
        inventario: producto.id,
        bodega: bodegaSeleccionada,
        cantidad,
      });

      setExito(`✅ Despachado: ${cantidad} x ${producto.nombre}.`);
      cargarDatos();
      setTimeout(() => setExito(''), 2500);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'No se pudo registrar el despacho.');
    } finally {
      setDespachando(null);
    }
  };

  const statsDe = (productoId) => estadisticas.find((s) => s.inventario_id === productoId);

  return (
    <div className="despacho-wrapper">
      <div className="header-status">
        <h1 className="page-title">
          <FaBolt /> Despacho Rápido
        </h1>

        <div className={`network-badge ${isOffline ? 'badge-offline' : 'badge-online'}`}>
          {isOffline ? (<><FaSignal /> Modo Offline</>) : (<><FaWifi /> Conectado</>)}
        </div>
      </div>

      <p className="page-subtitle">
        Para consumibles de alta rotación (ej. agua): un clic descuenta el stock al instante, sin RUT ni firma.
      </p>

      {error && <div className="alert alert-error">{error}</div>}
      {exito && <div className="alert alert-success">{exito}</div>}

      <div className="step-card">
        <div className="step-header">
          <span>BODEGA</span>
          <FaMapMarkerAlt />
        </div>

        <div className="step-body">
          <select
            className="custom-select"
            value={bodegaSeleccionada}
            onChange={(e) => setBodegaSeleccionada(e.target.value)}
            disabled={isOffline}
          >
            <option value="">-- Seleccione bodega --</option>
            {bodegas.map((b) => (
              <option key={b.id} value={b.id}>{b.nombre}</option>
            ))}
          </select>
        </div>
      </div>

      {isOffline ? (
        <div className="text-center-padded">Conéctate a internet para usar el despacho rápido.</div>
      ) : !bodegaSeleccionada ? (
        <div className="text-center-padded">Selecciona una bodega para ver sus productos de despacho rápido.</div>
      ) : productos.length === 0 ? (
        <div className="text-center-padded">
          No hay productos de despacho rápido en esta bodega. Márcalos desde Inventario
          (casilla "Despacho rápido").
        </div>
      ) : (
        <div className="despacho-grid">
          {productos.map((producto) => {
            const stats = statsDe(producto.id);

            return (
              <div key={producto.id} className="despacho-card">
                <div className="despacho-card-header">
                  <span className="despacho-nombre">{producto.nombre}</span>
                  <span className="despacho-codigo">{producto.codigo}</span>
                </div>

                <div className="despacho-stock">
                  Stock actual: <strong>{producto.stock_actual}</strong>
                </div>

                <div className="despacho-stats">
                  <FaChartBar />
                  <span>Hoy: <strong>{stats?.consumo_hoy ?? 0}</strong></span>
                  <span>Semana: <strong>{stats?.consumo_semana ?? 0}</strong></span>
                </div>

                <div className="despacho-botones">
                  <button
                    className="btn-despachar"
                    disabled={despachando === producto.id || Number(producto.stock_actual) < 1}
                    onClick={() => despachar(producto, 1)}
                  >
                    <FaCheckCircle /> Despachar 1
                  </button>
                </div>

                {Number(producto.stock_actual) < 1 && (
                  <div className="despacho-sin-stock">
                    <FaExclamationTriangle /> Sin stock
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default DespachoRapido;
