import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import SignatureCanvas from 'react-signature-canvas';
import {
  FaUser,
  FaSearch,
  FaPenFancy,
  FaHardHat,
  FaWifi,
  FaSignal,
  FaMapMarkerAlt,
  FaUserShield,
  FaSyncAlt,
  FaHourglassHalf,
  FaExternalLinkAlt,
  FaBroadcastTower,
} from 'react-icons/fa';

import api from '../../api';
import { db } from '../../db';
import { useGeolocalizacion } from '../../hooks/useGeolocalizacion';
import { sincronizarEntregasPendientes as sincronizarEntregasPendientesCompartido } from '../../services/entregasOffline';
import './Entregas.css';

const formatoCLP = new Intl.NumberFormat('es-CL', {
  style: 'currency',
  currency: 'CLP',
  maximumFractionDigits: 0,
});

const formatearCLP = (valor) => formatoCLP.format(Number(valor) || 0);

const Entregas = () => {
  const navigate = useNavigate();

  const [entregas, setEntregas] = useState([]);
  const [trabajadores, setTrabajadores] = useState([]);
  const [inventario, setInventario] = useState([]);
  const [bodegas, setBodegas] = useState([]);

  const [usuarioActual, setUsuarioActual] = useState({
    id: localStorage.getItem('user_id') ? Number(localStorage.getItem('user_id')) : null,
    username: localStorage.getItem('username') || '',
    rol: localStorage.getItem('user_role') || '',
  });

  const [error, setError] = useState('');
  const [exito, setExito] = useState('');
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  const [bodegaSeleccionada, setBodegaSeleccionada] = useState('');
  const [rutBusqueda, setRutBusqueda] = useState('');
  const [trabajadorSeleccionado, setTrabajadorSeleccionado] = useState(null);
  const [productosSeleccionados, setProductosSeleccionados] = useState({});
  const [unidadesDisponibles, setUnidadesDisponibles] = useState([]);
  const [unidadesSeleccionadas, setUnidadesSeleccionadas] = useState({});
  const [busquedaProducto, setBusquedaProducto] = useState('');

  const sigCanvas = useRef({});
  const { capturar: capturarGeolocalizacion, estado: estadoGps, error: errorGps } = useGeolocalizacion();

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

    cargarUsuarioActual();
    cargarDatos();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const cargarUsuarioActual = async () => {
    if (usuarioActual.id) return;
    if (!navigator.onLine) return;

    try {
      const res = await api.get('/me/');

      localStorage.setItem('user_id', res.data.id);
      localStorage.setItem('username', res.data.username);
      localStorage.setItem('user_role', res.data.rol_nombre || '');

      setUsuarioActual({
        id: res.data.id,
        username: res.data.username,
        rol: res.data.rol_nombre || '',
      });
    } catch (err) {
      console.error(err);
    }
  };

  const cargarDatos = async () => {
    try {
      if (!navigator.onLine) throw new Error('OFFLINE_REAL');

      const [resTrab, resInv, resBodegas, resEntregas, resUnidades] = await Promise.all([
        api.get('/trabajadores/'),
        api.get('/inventario/'),
        api.get('/bodegas/'),
        api.get('/entregas-epp/').catch(() => ({ data: [] })),
        api.get('/unidades-activo/?estado=DISPONIBLE').catch(() => ({ data: [] })),
      ]);

      setTrabajadores(resTrab.data);
      setInventario(resInv.data);
      setBodegas(resBodegas.data);
      setEntregas(resEntregas.data);
      setUnidadesDisponibles(resUnidades.data);

      await db.cache_trabajadores.bulkPut(resTrab.data);
      await db.cache_inventario.bulkPut(resInv.data);

      setIsOffline(false);
      setError('');
    } catch (err) {
      console.error(err);

      if (!navigator.onLine || err.message === 'OFFLINE_REAL') {
        setIsOffline(true);
        setError('Sin conexión. Operando con caché local (Modo Terreno).');

        const localTrab = await db.cache_trabajadores.toArray();
        const localInv = await db.cache_inventario.toArray();

        setTrabajadores(localTrab);
        setInventario(localInv);
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

    await sincronizarEntregasPendientesCompartido();

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

  const toggleUnidad = (unidad) => {
    setUnidadesSeleccionadas((prev) => {
      const nuevo = { ...prev };

      if (nuevo[unidad.id]) {
        delete nuevo[unidad.id];
      } else {
        nuevo[unidad.id] = {
          inventario_id: unidad.inventario,
          codigo: unidad.codigo,
          producto_nombre: unidad.producto_nombre,
        };
      }

      return nuevo;
    });
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
    setUnidadesSeleccionadas({});
    setBodegaSeleccionada('');
    setBusquedaProducto('');

    if (sigCanvas.current) {
      sigCanvas.current.clear();
    }
  };

  const textoBusqueda = busquedaProducto.toLowerCase().trim();

  const productosDisponibles = inventario.filter((item) => {
    if (!bodegaSeleccionada) return false;
    if (item.es_devolutivo) return false;
    if (String(item.bodega) !== String(bodegaSeleccionada)) return false;
    if (Number(item.stock_actual) <= 0) return false;

    if (!textoBusqueda) return true;

    return (
      item.nombre?.toLowerCase().includes(textoBusqueda) ||
      item.codigo?.toLowerCase().includes(textoBusqueda)
    );
  });

  const unidadesEnBodega = unidadesDisponibles.filter((unidad) => {
    if (!bodegaSeleccionada) return false;
    if (String(unidad.bodega) !== String(bodegaSeleccionada)) return false;

    if (!textoBusqueda) return true;

    return (
      unidad.codigo?.toLowerCase().includes(textoBusqueda) ||
      unidad.producto_nombre?.toLowerCase().includes(textoBusqueda)
    );
  });

  const fechaVencimiento = (vidaUtilDias) => {
    if (!vidaUtilDias) return null;
    const fecha = new Date();
    fecha.setDate(fecha.getDate() + Number(vidaUtilDias));
    return fecha.toLocaleDateString();
  };

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

    const hayUnidades = Object.keys(unidadesSeleccionadas).length > 0;

    if (!usuarioActual.id) return setError('⚠️ No se pudo identificar al responsable de la entrega. Vuelve a iniciar sesión.');
    if (!bodegaSeleccionada) return setError('⚠️ Seleccione la bodega.');
    if (!trabajadorSeleccionado) return setError('⚠️ Debe buscar y seleccionar un trabajador.');
    if (Object.keys(productosSeleccionados).length === 0 && !hayUnidades) {
      return setError('⚠️ Seleccione al menos un producto o equipo a entregar.');
    }
    if (sigCanvas.current.isEmpty()) {
      return setError('⚠️ La firma del trabajador es obligatoria.');
    }
    if (hayUnidades && (isOffline || !navigator.onLine)) {
      return setError(
        '⚠️ Los radios y equipos devolutivos requieren conexión para evitar asignar el mismo equipo dos veces.'
      );
    }

    const errorStock = validarStockSeleccionado();
    if (errorStock) return setError(`⚠️ ${errorStock}`);

    const firmaBase64 = sigCanvas.current.getCanvas().toDataURL('image/png');

    // Se captura recién al confirmar (no antes): es la coordenada más
    // cercana posible al instante real de la entrega. Si el GPS falla o el
    // permiso está denegado, geolocalizacion queda en null y la entrega
    // igual se registra (la firma es la evidencia obligatoria, el GPS es
    // evidencia adicional).
    const geolocalizacion = await capturarGeolocalizacion();

    const detallesProductos = Object.keys(productosSeleccionados).map((productoId) => ({
      inventario: parseInt(productoId),
      cantidad: productosSeleccionados[productoId],
      talla: 'N/A',
    }));

    const detallesUnidades = Object.keys(unidadesSeleccionadas).map((unidadId) => ({
      inventario: unidadesSeleccionadas[unidadId].inventario_id,
      cantidad: 1,
      talla: 'N/A',
      unidad_activo: parseInt(unidadId),
    }));

    const payloadLocal = {
      usuario_id: usuarioActual.id,
      bodega_id: parseInt(bodegaSeleccionada),
      trabajador_id: trabajadorSeleccionado.id,
      productos: productosSeleccionados,
      firma_base64: firmaBase64,
      fecha: new Date().toISOString(),
      latitud: geolocalizacion?.latitud ?? null,
      longitud: geolocalizacion?.longitud ?? null,
      precision_metros: geolocalizacion?.precision_metros ?? null,
      geolocalizacion_capturada_en: geolocalizacion?.geolocalizacion_capturada_en ?? null,
      sincronizado: 0,
    };

    const payloadServidor = {
      trabajador: payloadLocal.trabajador_id,
      usuario: payloadLocal.usuario_id,
      bodega: payloadLocal.bodega_id,
      firma_base64: payloadLocal.firma_base64,
      observacion: `Entrega a ${trabajadorSeleccionado.nombres} ${trabajadorSeleccionado.apellido_paterno} | RUT ${trabajadorSeleccionado.rut}`,
      estado: 'COMPLETADA',
      latitud: payloadLocal.latitud,
      longitud: payloadLocal.longitud,
      precision_metros: payloadLocal.precision_metros,
      geolocalizacion_capturada_en: payloadLocal.geolocalizacion_capturada_en,
      detalles: [...detallesProductos, ...detallesUnidades],
    };

    try {
      if (!isOffline && navigator.onLine) {
        await api.post('/entregas-epp/', payloadServidor);

        if (hayUnidades) {
          const codigos = Object.values(unidadesSeleccionadas).map((u) => u.codigo).join(', ');
          setExito(`✅ Entrega registrada. Recuerda: ${codigos} debe(n) devolverse al finalizar el turno.`);
        } else {
          setExito('✅ Entrega registrada, historial creado y stock descontado correctamente.');
        }
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
      setTimeout(() => setExito(''), 5000);
    } catch (err) {
      console.error(err);

      if (!navigator.onLine) {
        setIsOffline(true);

        if (hayUnidades) {
          setError(
            '❌ Se perdió la conexión al registrar la entrega. No se pudo confirmar si el/los equipo(s) ' +
            `(${Object.values(unidadesSeleccionadas).map((u) => u.codigo).join(', ')}) quedaron asignados. ` +
            'Verifica en Devoluciones antes de reintentar para no duplicar la entrega.'
          );
          return;
        }

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

      <div className="responsable-banner">
        <FaUserShield />
        <div>
          <span className="responsable-label">Registrando entrega como</span>
          <strong className="responsable-nombre">
            {usuarioActual.username || 'Usuario no identificado'}
            {usuarioActual.rol ? ` · ${usuarioActual.rol}` : ''}
          </strong>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {exito && <div className="alert alert-success">{exito}</div>}

      <div className="step-card">
        <div className="step-header">
          <span>1. BODEGA DE ENTREGA</span>
          <FaMapMarkerAlt />
        </div>

        <div className="step-body">
          <select
            className="custom-select"
            value={bodegaSeleccionada}
            onChange={(e) => {
              setBodegaSeleccionada(e.target.value);
              setProductosSeleccionados({});
              setUnidadesSeleccionadas({});
              setBusquedaProducto('');
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
          <span>2. IDENTIFICACIÓN TRABAJADOR</span>
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
            <div className="step-header">3. SELECCIÓN DE PRODUCTOS / EPP</div>

            <div className="step-body">
              {!bodegaSeleccionada ? (
                <div className="text-center-padded">Seleccione una bodega primero.</div>
              ) : (
                <>
                  <div className="search-input-wrapper product-search">
                    <span className="search-icon-box">
                      <FaSearch />
                    </span>

                    <input
                      type="text"
                      placeholder="Buscar producto por nombre o código..."
                      value={busquedaProducto}
                      onChange={(e) => setBusquedaProducto(e.target.value)}
                    />
                  </div>

                  {productosDisponibles.length === 0 ? (
                    <div className="text-center-padded">
                      No hay productos con stock disponible que coincidan con la búsqueda.
                    </div>
                  ) : (
                    <div className="epp-list">
                      {productosDisponibles.map((producto) => {
                        const isSelected = !!productosSeleccionados[producto.id];
                        const vencimiento = fechaVencimiento(producto.vida_util_dias);

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

                              <div>
                                <span>
                                  {producto.nombre}
                                  <small className="epp-stock-info">
                                    {' '}
                                    [{producto.codigo}] Stock: {producto.stock_actual}
                                  </small>
                                </span>

                                <div className="epp-tags">
                                  {producto.es_devolutivo && (
                                    <span className="tag-devolutivo">
                                      <FaSyncAlt /> Devolutivo
                                    </span>
                                  )}

                                  {vencimiento && (
                                    <span className="tag-vencimiento">
                                      <FaHourglassHalf /> Vence: {vencimiento}
                                    </span>
                                  )}
                                </div>
                              </div>
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

                  <div className="devolutivos-apartado">
                    <div className="apartado-header">
                      <FaBroadcastTower /> Radios y Equipos Devolutivos
                    </div>

                    {unidadesEnBodega.length === 0 ? (
                      <div className="text-center-padded">
                        No hay equipos devolutivos disponibles en esta bodega. Agrégalos desde{' '}
                        <strong>Inventario</strong> (marca el producto como devolutivo y crea sus unidades).
                      </div>
                    ) : (
                      <div className="epp-list">
                        {unidadesEnBodega.map((unidad) => {
                          const isSelected = !!unidadesSeleccionadas[unidad.id];

                          return (
                            <div
                              key={unidad.id}
                              className={`epp-item unidad-radio ${isSelected ? 'selected' : ''}`}
                              onClick={() => toggleUnidad(unidad)}
                            >
                              <div className="epp-item-left">
                                <input
                                  type="checkbox"
                                  className="epp-checkbox"
                                  checked={isSelected}
                                  readOnly
                                />

                                <div>
                                  <span className="unidad-radio-codigo">{unidad.codigo}</span>
                                  <div className="epp-tags">
                                    <span className="tag-devolutivo">
                                      <FaSyncAlt /> {unidad.producto_nombre}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {Object.keys(unidadesSeleccionadas).length > 0 && (
                    <div className="aviso-devolutivo">
                      <FaSyncAlt />
                      <span>
                        {Object.values(unidadesSeleccionadas).map((u) => u.codigo).join(', ')} debe(n)
                        devolverse al finalizar el turno. Podrás registrarlo en{' '}
                        <button
                          type="button"
                          className="link-devoluciones"
                          onClick={() => navigate('/devoluciones')}
                        >
                          Devoluciones <FaExternalLinkAlt />
                        </button>
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="step-card">
            <div className="step-header">
              <span>4. FIRMA DIGITAL DEL TRABAJADOR</span>
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
                </div>

                <button className="btn-clear-sig" onClick={limpiarFirma}>
                  Borrar firma
                </button>
              </div>
            </div>
          </div>

          <div className="gps-status-line">
            <FaMapMarkerAlt />
            {estadoGps === 'capturando' && <span>Obteniendo ubicación GPS...</span>}
            {estadoGps === 'ok' && <span>Ubicación GPS capturada para auditoría.</span>}
            {estadoGps === 'error' && <span title={errorGps}>Sin GPS disponible: la entrega se registrará igual.</span>}
            {estadoGps === 'inactivo' && <span>La ubicación se captura al confirmar la entrega.</span>}
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
              <th>Ítems</th>
              <th>Valor</th>
              <th>Firma</th>
            </tr>
          </thead>

          <tbody>
            {entregas.length === 0 ? (
              <tr>
                <td colSpan="8" className="text-center-padded">
                  No hay entregas registradas.
                </td>
              </tr>
            ) : (
              entregas.slice(0, 10).map((entrega) => {
                const detalles = entrega.detalles || [];
                const tieneDevolutivo = detalles.some((d) => d.es_devolutivo && !d.devuelto);
                const tieneVencimientoProximo = detalles.some(
                  (d) => d.dias_para_vencer !== null && d.dias_para_vencer !== undefined && d.dias_para_vencer <= 30
                );

                return (
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

                    <td>
                      <div className="epp-tags">
                        {tieneDevolutivo && (
                          <span className="tag-devolutivo" title="Contiene ítems devolutivos pendientes">
                            <FaSyncAlt />
                          </span>
                        )}
                        {tieneVencimientoProximo && (
                          <span className="tag-vencimiento" title="Contiene EPP próximo a vencer">
                            <FaHourglassHalf />
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="fw-bold">
                      {formatearCLP(
                        entrega.valor_total ?? detalles.reduce((t, d) => t + (Number(d.subtotal) || 0), 0)
                      )}
                    </td>

                    <td>
                      {entrega.firma_base64 ? (
                        <img
                          src={entrega.firma_base64}
                          alt={`Firma de ${entrega.trabajador_nombre || 'trabajador'}`}
                          className="history-signature-img"
                        />
                      ) : (
                        <span className="text-muted">Sin firma</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Entregas;
