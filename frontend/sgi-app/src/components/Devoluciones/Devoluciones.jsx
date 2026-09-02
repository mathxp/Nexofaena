import { useState, useEffect, useRef } from 'react';
import {
  FaUndo,
  FaWifi,
  FaSignal,
  FaMapMarkerAlt,
  FaCheckCircle,
  FaExclamationTriangle,
  FaUserFriends,
  FaTools,
} from 'react-icons/fa';

import api from '../../api';
import './Devoluciones.css';

const Devoluciones = () => {
  const [bodegas, setBodegas] = useState([]);
  const [bodegaSeleccionada, setBodegaSeleccionada] = useState('');
  const [pendientes, setPendientes] = useState([]);
  const [devueltosHoy, setDevueltosHoy] = useState([]);
  const [estadosSeleccionados, setEstadosSeleccionados] = useState({});

  const bodegaActualRef = useRef(bodegaSeleccionada);
  useEffect(() => { bodegaActualRef.current = bodegaSeleccionada; }, [bodegaSeleccionada]);

  const [error, setError] = useState('');
  const [exito, setExito] = useState('');
  const [cargando, setCargando] = useState(false);
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
      cargarPendientes();
    } else {
      setPendientes([]);
      setDevueltosHoy([]);
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

  const cargarPendientes = async () => {
    if (!navigator.onLine) {
      setIsOffline(true);
      setError('Sin conexión. Las devoluciones requieren conexión para actualizar el stock en el servidor.');
      return;
    }

    try {
      setCargando(true);
      setError('');

      const [resPendientes, resDevueltos] = await Promise.all([
        api.get(`/detalles-entrega-epp/?bodega=${bodegaSeleccionada}&pendientes=true`),
        api.get(`/detalles-entrega-epp/?bodega=${bodegaSeleccionada}&pendientes=false`),
      ]);

      setPendientes(resPendientes.data);
      setDevueltosHoy(resDevueltos.data.slice(0, 10));
      setIsOffline(false);
    } catch (err) {
      console.error(err);

      if (!navigator.onLine) {
        setIsOffline(true);
        setError('Sin conexión. Las devoluciones requieren conexión para actualizar el stock en el servidor.');
      } else {
        setError('Error al cargar los activos devolutivos de esta bodega.');
      }
    } finally {
      setCargando(false);
    }
  };

  const marcarDevuelto = async (detalle) => {
    if (!navigator.onLine) {
      setError('⚠️ No es posible registrar devoluciones sin conexión.');
      return;
    }

    setError('');
    setExito('');

    const bodegaAlSolicitar = bodegaSeleccionada;
    const estadoDevolucion = estadosSeleccionados[detalle.id] || 'OPERATIVA';

    try {
      await api.post(`/detalles-entrega-epp/${detalle.id}/devolver/`, {
        estado_devolucion: estadoDevolucion,
      });
      const etiqueta = detalle.unidad_activo_codigo || detalle.producto_nombre;
      const nota = estadoDevolucion === 'DAÑADA' ? ' (marcada DAÑADA, pasa a mantención)' : '';
      setExito(`✅ ${etiqueta} de ${detalle.trabajador_nombre} registrado como devuelto${nota}.`);

      // Si el usuario ya cambió de bodega mientras esta solicitud estaba en
      // vuelo, el efecto de esa selección ya cargó los datos correctos:
      // recargar aquí pisaría esa lista con la de la bodega anterior.
      if (bodegaActualRef.current === bodegaAlSolicitar) {
        cargarPendientes();
      }

      setTimeout(() => setExito(''), 3000);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Error al registrar la devolución.');
    }
  };

  return (
    <div className="devoluciones-wrapper">
      <div className="header-status">
        <h1 className="page-title">
          <FaUndo /> Devoluciones de Activos Diarios
        </h1>

        <div className={`network-badge ${isOffline ? 'badge-offline' : 'badge-online'}`}>
          {isOffline ? (
            <>
              <FaSignal /> Modo Offline
            </>
          ) : (
            <>
              <FaWifi /> Conectado
            </>
          )}
        </div>
      </div>

      <p className="page-subtitle">
        Registra el retorno de equipos devolutivos (radios y similares) al finalizar el turno para recuperar el stock.
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
              <option key={b.id} value={b.id}>
                {b.nombre}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isOffline ? (
        <div className="text-center-padded">
          Conéctate a internet para ver y registrar devoluciones.
        </div>
      ) : !bodegaSeleccionada ? (
        <div className="text-center-padded">Selecciona una bodega para ver sus activos pendientes de devolución.</div>
      ) : (
        <>
          <h3 className="history-title">
            Pendientes de Devolución {cargando && '(cargando...)'}
          </h3>

          <div className="devoluciones-list">
            {pendientes.length === 0 ? (
              <div className="text-center-padded">
                <FaCheckCircle /> No hay activos pendientes de devolución en esta bodega.
              </div>
            ) : (
              pendientes.map((detalle) => (
                <div key={detalle.id} className="devolucion-item">
                  <div className="devolucion-info">
                    <div className="devolucion-producto">
                      {detalle.unidad_activo_codigo ? (
                        <>
                          <span className="devolucion-codigo">{detalle.unidad_activo_codigo}</span>
                          {' · '}{detalle.producto_nombre}
                        </>
                      ) : (
                        <>
                          {detalle.producto_nombre}
                          <span className="devolucion-cantidad"> x{detalle.cantidad}</span>
                        </>
                      )}
                    </div>

                    <div className="devolucion-trabajador">
                      <FaUserFriends /> {detalle.trabajador_nombre} ({detalle.trabajador_rut})
                    </div>
                  </div>

                  <div className="devolucion-acciones">
                    <div className="estado-toggle">
                      <button
                        type="button"
                        className={`estado-toggle-btn ${(estadosSeleccionados[detalle.id] || 'OPERATIVA') === 'OPERATIVA' ? 'activo' : ''}`}
                        onClick={() => setEstadosSeleccionados((prev) => ({ ...prev, [detalle.id]: 'OPERATIVA' }))}
                      >
                        <FaCheckCircle /> Operativa
                      </button>
                      <button
                        type="button"
                        className={`estado-toggle-btn danio ${estadosSeleccionados[detalle.id] === 'DAÑADA' ? 'activo' : ''}`}
                        onClick={() => setEstadosSeleccionados((prev) => ({ ...prev, [detalle.id]: 'DAÑADA' }))}
                      >
                        <FaTools /> Dañada
                      </button>
                    </div>

                    <button className="btn-marcar-devuelto" onClick={() => marcarDevuelto(detalle)}>
                      Marcar Devuelto
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <h3 className="history-title">Devoluciones Recientes</h3>

          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Trabajador</th>
                  <th>Estado</th>
                  <th>Fecha Devolución</th>
                </tr>
              </thead>

              <tbody>
                {devueltosHoy.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="text-center-padded">
                      <FaExclamationTriangle /> Aún no hay devoluciones registradas.
                    </td>
                  </tr>
                ) : (
                  devueltosHoy.map((detalle) => (
                    <tr key={detalle.id}>
                      <td className="fw-bold">
                        {detalle.unidad_activo_codigo
                          ? `${detalle.unidad_activo_codigo} · ${detalle.producto_nombre}`
                          : detalle.producto_nombre}
                      </td>
                      <td>{detalle.trabajador_nombre}</td>
                      <td>
                        {detalle.estado_devolucion === 'DAÑADA' ? (
                          <span className="badge-danada"><FaTools /> Dañada</span>
                        ) : (
                          <span className="badge-operativa"><FaCheckCircle /> Operativa</span>
                        )}
                      </td>
                      <td>{new Date(detalle.fecha_devolucion).toLocaleString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

export default Devoluciones;
