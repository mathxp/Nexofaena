import { useState, useEffect, useRef } from 'react';
import SignatureCanvas from 'react-signature-canvas';
import {
  FaUser,
  FaSearch,
  FaPenFancy,
  FaHardHat,
  FaWifi,
  FaSignal,
  FaMapMarkerAlt,
} from 'react-icons/fa';

import api from '../../api';
import { db } from '../../db';
import './Entregas.css';

const Entregas = () => {
  const [entregas, setEntregas] = useState([]);
  const [trabajadores, setTrabajadores] = useState([]);
  const [inventario, setInventario] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [bodegas, setBodegas] = useState([]);

  const [error, setError] = useState('');
  const [exito, setExito] = useState('');
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  const [usuarioSeleccionado, setUsuarioSeleccionado] = useState('');
  const [bodegaSeleccionada, setBodegaSeleccionada] = useState('');
  const [rutBusqueda, setRutBusqueda] = useState('');
  const [trabajadorSeleccionado, setTrabajadorSeleccionado] = useState(null);
  const [productosSeleccionados, setProductosSeleccionados] = useState({});

  const sigCanvas = useRef({});

  useEffect(() => {
    const handleOnline = () => {
      setIsOffline(false);
      sincronizarEntregasPendientes();
      cargarDatos();
    };

    const handleOffline = () => {
      setIsOffline(true);
      setError('Sin conexión. Operando con caché local (Modo Terreno).');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    cargarDatos();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const cargarDatos = async () => {
    try {
      if (!navigator.onLine) throw new Error('OFFLINE_REAL');

      const [resTrab, resInv, resUsuarios, resBodegas, resEntregas] = await Promise.all([
        api.get('/trabajadores/'),
        api.get('/inventario/'),
        api.get('/usuarios/').catch(() => ({ data: [] })),
        api.get('/bodegas/'),
        api.get('/entregas-epp/').catch(() => ({ data: [] })),
      ]);

      setTrabajadores(resTrab.data);
      setInventario(resInv.data);
      setUsuarios(resUsuarios.data);
      setBodegas(resBodegas.data);
      setEntregas(resEntregas.data);

      await db.cache_trabajadores.bulkPut(resTrab.data);
      await db.cache_inventario.bulkPut(resInv.data);
      await db.cache_usuarios.bulkPut(resUsuarios.data);

      setIsOffline(false);
      setError('');
    } catch (err) {
      console.error(err);

      if (!navigator.onLine || err.message === 'OFFLINE_REAL') {
        setIsOffline(true);
        setError('Sin conexión. Operando con caché local (Modo Terreno).');

        const localTrab = await db.cache_trabajadores.toArray();
        const localInv = await db.cache_inventario.toArray();
        const localUsu = await db.cache_usuarios.toArray();

        setTrabajadores(localTrab);
        setInventario(localInv);
        setUsuarios(localUsu);
        return;
      }

      setIsOffline(false);

      if (err.response?.status === 401) {
        setError('Sesión expirada o no autorizada. Inicia sesión nuevamente.');
      } else {
        setError('Error al cargar datos del servidor. Revisa rutas del backend.');
      }
    }
  };

  const sincronizarEntregasPendientes = async () => {
    const pendientes = await db.entregas_pendientes.where({ sincronizado: 0 }).toArray();
    if (pendientes.length === 0) return;

    setExito(`Sincronizando ${pendientes.length} entregas pendientes...`);

    for (const entrega of pendientes) {
      try {
        await api.post('/entregas-epp/', {
          trabajador: entrega.trabajador_id,
          usuario: entrega.usuario_id,
          bodega: entrega.bodega_id,
          firma_base64: entrega.firma_base64,
          observacion: 'Entrega sincronizada desde modo offline',
          estado: 'COMPLETADA',
          detalles: Object.keys(entrega.productos).map((productoId) => ({
            inventario: parseInt(productoId),
            cantidad: entrega.productos[productoId],
            talla: 'N/A',
          })),
        });

        await db.entregas_pendientes.delete(entrega.id);
      } catch (err) {
        console.error('Error sincronizando entrega:', err);
      }
    }

    cargarDatos();
    setExito('✅ Sincronización offline completada.');
    setTimeout(() => setExito(''), 3000);
  };

  const handleBuscarRut = () => {
    setError('');
    setExito('');

    const texto = rutBusqueda.toLowerCase().trim();

    const encontrado = trabajadores.find((t) =>
      t.rut?.toLowerCase().includes(texto)
    );

    if (encontrado) {
      setTrabajadorSeleccionado(encontrado);
    } else {
      setTrabajadorSeleccionado(null);
      setError('❌ Trabajador no encontrado.');
    }
  };

  const toggleProducto = (id) => {
    setProductosSeleccionados((prev) => {
      const nuevo = { ...prev };

      if (nuevo[id]) {
        delete nuevo[id];
      } else {
        nuevo[id] = 1;
      }

      return nuevo;
    });
  };

  const updateCantidad = (id, cantidad) => {
    const valor = Number(cantidad);
    if (valor < 1) return;

    setProductosSeleccionados((prev) => ({
      ...prev,
      [id]: valor,
    }));
  };

  const limpiarFirma = (e) => {
    e.preventDefault();
    sigCanvas.current.clear();
  };

  const limpiarFormulario = () => {
    setTrabajadorSeleccionado(null);
    setRutBusqueda('');
    setProductosSeleccionados({});
    setUsuarioSeleccionado('');
    setBodegaSeleccionada('');

    if (sigCanvas.current) {
      sigCanvas.current.clear();
    }
  };

  const productosDisponibles = inventario.filter((item) => {
    if (!bodegaSeleccionada) return false;
    return String(item.bodega) === String(bodegaSeleccionada) && Number(item.stock_actual) > 0;
  });

  const validarStockSeleccionado = () => {
    for (const productoId of Object.keys(productosSeleccionados)) {
      const producto = inventario.find((p) => String(p.id) === String(productoId));
      const cantidad = Number(productosSeleccionados[productoId]);

      if (!producto) return `Producto ID ${productoId} no encontrado.`;
      if (cantidad <= 0) return `Cantidad inválida para ${producto.nombre}.`;
      if (cantidad > Number(producto.stock_actual)) {
        return `Stock insuficiente para ${producto.nombre}. Disponible: ${producto.stock_actual}`;
      }
    }

    return null;
  };

  const handleSubmit = async () => {
    setError('');
    setExito('');

    if (!usuarioSeleccionado) return setError('⚠️ Seleccione el responsable de la entrega.');
    if (!bodegaSeleccionada) return setError('⚠️ Seleccione la bodega.');
    if (!trabajadorSeleccionado) return setError('⚠️ Debe buscar y seleccionar un trabajador.');
    if (Object.keys(productosSeleccionados).length === 0) {
      return setError('⚠️ Seleccione al menos un producto a entregar.');
    }
    if (sigCanvas.current.isEmpty()) {
      return setError('⚠️ La firma del trabajador es obligatoria.');
    }

    const errorStock = validarStockSeleccionado();
    if (errorStock) return setError(`⚠️ ${errorStock}`);

    const firmaBase64 = sigCanvas.current.getCanvas().toDataURL('image/png');

    const payloadLocal = {
      usuario_id: parseInt(usuarioSeleccionado),
      bodega_id: parseInt(bodegaSeleccionada),
      trabajador_id: trabajadorSeleccionado.id,
      productos: productosSeleccionados,
      firma_base64: firmaBase64,
      fecha: new Date().toISOString(),
      sincronizado: 0,
    };

    const payloadServidor = {
      trabajador: payloadLocal.trabajador_id,
      usuario: payloadLocal.usuario_id,
      bodega: payloadLocal.bodega_id,
      firma_base64: payloadLocal.firma_base64,
      observacion: `Entrega a ${trabajadorSeleccionado.nombres} ${trabajadorSeleccionado.apellido_paterno} | RUT ${trabajadorSeleccionado.rut}`,
      estado: 'COMPLETADA',
      detalles: Object.keys(productosSeleccionados).map((productoId) => ({
        inventario: parseInt(productoId),
        cantidad: productosSeleccionados[productoId],
        talla: 'N/A',
      })),
    };

    try {
      if (!isOffline && navigator.onLine) {
        await api.post('/entregas-epp/', payloadServidor);
        setExito('✅ Entrega registrada, historial creado y stock descontado correctamente.');
      } else {
        await db.entregas_pendientes.add(payloadLocal);

        for (const productoId of Object.keys(productosSeleccionados)) {
          const producto = await db.cache_inventario.get(parseInt(productoId));

          if (producto) {
            const nuevoStock =
              Number(producto.stock_actual) - Number(productosSeleccionados[productoId]);

            await db.cache_inventario.update(parseInt(productoId), {
              stock_actual: nuevoStock,
            });
          }
        }

        setExito('📡 Entrega guardada localmente. Se sincronizará al recuperar conexión.');
      }

      limpiarFormulario();
      cargarDatos();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      setTimeout(() => setExito(''), 3000);
    } catch (err) {
      console.error(err);

      if (!navigator.onLine) {
        setIsOffline(true);
        await db.entregas_pendientes.add(payloadLocal);
        setExito('Red inestable. Entrega resguardada localmente.');
        limpiarFormulario();
        return;
      }

      if (err.response?.data?.detail) {
        setError(`❌ ${err.response.data.detail}`);
      } else {
        setError('❌ Error al registrar entrega. Revisa stock, usuario o permisos.');
      }
    }
  };

  return (
    <div className="entregas-wrapper">
      <div className="header-status">
        <h1 className="page-title">Entrega de EPP</h1>

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

      {error && <div className="alert alert-error">{error}</div>}
      {exito && <div className="alert alert-success">{exito}</div>}

      <div className="step-card">
        <div className="step-header">
          <span>1. RESPONSABLE DE ENTREGA</span>
          <FaHardHat />
        </div>

        <div className="step-body">
          <select
            className="custom-select"
            value={usuarioSeleccionado}
            onChange={(e) => setUsuarioSeleccionado(e.target.value)}
          >
            <option value="">-- Seleccione usuario responsable --</option>
            {usuarios.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username} {u.rut ? `(${u.rut})` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="step-card">
        <div className="step-header">
          <span>2. BODEGA DE ENTREGA</span>
          <FaMapMarkerAlt />
        </div>

        <div className="step-body">
          <select
            className="custom-select"
            value={bodegaSeleccionada}
            onChange={(e) => {
              setBodegaSeleccionada(e.target.value);
              setProductosSeleccionados({});
            }}
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

      <div className="step-card">
        <div className="step-header">
          <span>3. IDENTIFICACIÓN TRABAJADOR</span>
          <FaUser />
        </div>

        <div className="step-body">
          <div className="search-input-wrapper">
            <span className="search-icon-box">
              <FaSearch />
            </span>

            <input
              type="text"
              placeholder="Ingrese RUT del trabajador"
              value={rutBusqueda}
              onChange={(e) => setRutBusqueda(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleBuscarRut()}
            />

            <button className="btn-buscar-rut" onClick={handleBuscarRut}>
              BUSCAR
            </button>
          </div>
        </div>
      </div>

      {trabajadorSeleccionado && (
        <>
          <div className="step-card">
            <div className="step-header">DATOS DEL TRABAJADOR</div>

            <div className="step-body">
              <div className="worker-data-grid">
                <span className="data-label">Nombre:</span>
                <span className="data-value">
                  {trabajadorSeleccionado.nombres} {trabajadorSeleccionado.apellido_paterno}
                </span>

                <span className="data-label">RUT:</span>
                <span className="data-value">{trabajadorSeleccionado.rut}</span>

                <span className="data-label">Cargo:</span>
                <span className="data-value">{trabajadorSeleccionado.cargo}</span>
              </div>
            </div>
          </div>

          <div className="step-card">
            <div className="step-header">4. SELECCIÓN DE PRODUCTOS / EPP</div>

            <div className="step-body">
              {!bodegaSeleccionada ? (
                <div className="text-center-padded">Seleccione una bodega primero.</div>
              ) : productosDisponibles.length === 0 ? (
                <div className="text-center-padded">
                  No hay productos con stock disponible en esta bodega.
                </div>
              ) : (
                <div className="epp-list">
                  {productosDisponibles.map((producto) => {
                    const isSelected = !!productosSeleccionados[producto.id];

                    return (
                      <div
                        key={producto.id}
                        className={`epp-item ${isSelected ? 'selected' : ''}`}
                      >
                        <div
                          className="epp-item-left"
                          onClick={() => toggleProducto(producto.id)}
                        >
                          <input
                            type="checkbox"
                            className="epp-checkbox"
                            checked={isSelected}
                            readOnly
                          />

                          <span>
                            {producto.nombre}
                            <small className="epp-stock-info">
                              {' '}
                              [{producto.codigo}] Stock: {producto.stock_actual}
                            </small>
                          </span>
                        </div>

                        {isSelected && (
                          <input
                            type="number"
                            className="epp-qty-input"
                            value={productosSeleccionados[producto.id]}
                            onChange={(e) => updateCantidad(producto.id, e.target.value)}
                            min="1"
                            max={producto.stock_actual}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="step-card">
            <div className="step-header">
              <span>5. FIRMA DIGITAL DEL TRABAJADOR</span>
              <FaPenFancy />
            </div>

            <div className="step-body step-body-padded">
              <div className="signature-container">
                <div className="signature-instructions">
                  Firme dentro del cuadro con dedo o mouse para confirmar la recepción.
                </div>

                <div className="signature-pad-wrapper">
                  <SignatureCanvas
                    ref={sigCanvas}
                    penColor="#001529"
                    canvasProps={{ className: 'sigCanvas' }}
                  />

                  <div className="signature-line">
                    <span>Firme Aquí</span>
                  </div>
                </div>

                <button className="btn-clear-sig" onClick={limpiarFirma}>
                  Borrar firma
                </button>
              </div>
            </div>
          </div>

          <button className="btn-confirmar-main" onClick={handleSubmit}>
            CONFIRMAR ENTREGA
          </button>
        </>
      )}

      <h3 className="history-title">Historial Reciente {isOffline && '(Local)'}</h3>

      <div className="history-table-wrapper">
        <table className="history-table">
          <thead>
            <tr>
              <th>Nº</th>
              <th>Trabajador</th>
              <th>Bodega</th>
              <th>Fecha</th>
              <th>Estado</th>
            </tr>
          </thead>

          <tbody>
            {entregas.length === 0 ? (
              <tr>
                <td colSpan="5" className="text-center-padded">
                  No hay entregas registradas.
                </td>
              </tr>
            ) : (
              entregas.slice(0, 10).map((entrega) => (
                <tr key={entrega.id}>
                  <td>
                    <strong>#{entrega.id}</strong>
                  </td>

                  <td className="fw-bold">
                    {entrega.trabajador_nombre || entrega.trabajador_rut || 'N/A'}
                  </td>

                  <td>{entrega.bodega_nombre || 'N/A'}</td>

                  <td>{new Date(entrega.fecha_entrega || entrega.fecha).toLocaleString()}</td>

                  <td>{entrega.estado || 'Registrada'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Entregas;