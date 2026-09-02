import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FaSearch,
  FaExclamationTriangle,
  FaFilter,
  FaMapMarkerAlt,
  FaPlus,
  FaEdit,
  FaTrashAlt,
  FaBarcode,
  FaTimes,
  FaBan,
  FaSyncAlt,
  FaHourglassHalf,
  FaChevronLeft,
  FaChevronRight,
  FaExternalLinkAlt,
  FaBolt,
  FaTools,
} from 'react-icons/fa';
import api from '../../api';
import './Inventario.css';

const PRODUCTOS_POR_PAGINA = 12;

const estadoInicial = {
  bodega: '',
  codigo: '',
  nombre: '',
  descripcion: '',
  stock_actual: '',
  stock_minimo: '',
  stock_maximo: '',
  ubicacion: '',
  estado: true,
  vida_util_dias: '',
  es_devolutivo: false,
  es_activo_critico: false,
  es_despacho_rapido: false,
};

const Inventario = () => {
  const navigate = useNavigate();

  const [productos, setProductos] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [movimientos, setMovimientos] = useState([]);
  const [error, setError] = useState('');
  const [erroresForm, setErroresForm] = useState({});

  const [searchTerm, setSearchTerm] = useState('');
  const [filtroBodega, setFiltroBodega] = useState('');
  const [soloReposicion, setSoloReposicion] = useState(false);
  const [paginaActual, setPaginaActual] = useState(1);

  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [modoEdicion, setModoEdicion] = useState(false);
  const [idEdicion, setIdEdicion] = useState(null);
  const [formData, setFormData] = useState(estadoInicial);

  const [productoUnidades, setProductoUnidades] = useState(null);
  const [unidades, setUnidades] = useState([]);
  const [nuevoCodigoUnidad, setNuevoCodigoUnidad] = useState('');
  const [errorUnidades, setErrorUnidades] = useState('');

  useEffect(() => {
    cargarDatos();
  }, []);

  useEffect(() => {
    setPaginaActual(1);
  }, [searchTerm, filtroBodega, soloReposicion]);

  const cargarDatos = async () => {
    try {
      const [resProductos, resBodegas, resMovs] = await Promise.all([
        api.get('/inventario/'),
        api.get('/bodegas/'),
        api.get('/movimientos/').catch(() => ({ data: [] })),
      ]);

      setProductos(resProductos.data);
      setBodegas(resBodegas.data);
      setMovimientos(resMovs.data);
    } catch {
      setError('Error al cargar datos del servidor.');
    }
  };

  const abrirPanelUnidades = async (producto) => {
    setProductoUnidades(producto);
    setNuevoCodigoUnidad('');
    setErrorUnidades('');

    try {
      const res = await api.get(`/unidades-activo/?inventario=${producto.id}`);
      setUnidades(res.data);
    } catch {
      setErrorUnidades('No se pudieron cargar las unidades de este producto.');
    }
  };

  const cerrarPanelUnidades = () => {
    setProductoUnidades(null);
    setUnidades([]);
    setNuevoCodigoUnidad('');
    setErrorUnidades('');
  };

  const agregarUnidad = async () => {
    setErrorUnidades('');

    if (!nuevoCodigoUnidad.trim()) {
      setErrorUnidades('Ingresa un código para la unidad (ej. RADIO-S001).');
      return;
    }

    try {
      await api.post('/unidades-activo/', {
        inventario: productoUnidades.id,
        codigo: nuevoCodigoUnidad.trim().toUpperCase(),
      });

      setNuevoCodigoUnidad('');
      await abrirPanelUnidades(productoUnidades);
      cargarDatos();
    } catch (err) {
      setErrorUnidades(err.response?.data?.detail || 'No se pudo crear la unidad.');
    }
  };

  const darDeBajaUnidad = async (unidad) => {
    if (!window.confirm(`¿Dar de baja la unidad ${unidad.codigo}? Esta acción no se puede deshacer.`)) return;

    setErrorUnidades('');

    try {
      await api.delete(`/unidades-activo/${unidad.id}/`);
      await abrirPanelUnidades(productoUnidades);
      cargarDatos();
    } catch (err) {
      setErrorUnidades(err.response?.data?.detail || 'No se pudo dar de baja la unidad.');
    }
  };

  const repararUnidad = async (unidad) => {
    setErrorUnidades('');

    try {
      await api.post(`/unidades-activo/${unidad.id}/reparar/`);
      await abrirPanelUnidades(productoUnidades);
    } catch (err) {
      setErrorUnidades(err.response?.data?.detail || 'No se pudo marcar la unidad como reparada.');
    }
  };

  const limpiarFormulario = () => {
    setMostrarFormulario(false);
    setModoEdicion(false);
    setIdEdicion(null);
    setFormData(estadoInicial);
    setErroresForm({});
    setError('');
  };

  const abrirCrear = () => {
    limpiarFormulario();
    setMostrarFormulario(true);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));

    setErroresForm((prev) => ({
      ...prev,
      [name]: '',
    }));
  };

  const cargarParaEdicion = (producto) => {
    setMostrarFormulario(true);
    setModoEdicion(true);
    setIdEdicion(producto.id);
    setErroresForm({});
    setError('');

    setFormData({
      bodega: producto.bodega || '',
      codigo: producto.codigo || '',
      nombre: producto.nombre || '',
      descripcion: producto.descripcion || '',
      stock_actual: producto.stock_actual ?? '',
      stock_minimo: producto.stock_minimo ?? '',
      stock_maximo: producto.stock_maximo ?? '',
      ubicacion: producto.ubicacion || '',
      estado: producto.estado ?? true,
      vida_util_dias: producto.vida_util_dias ?? '',
      es_devolutivo: producto.es_devolutivo ?? false,
      es_activo_critico: producto.es_activo_critico ?? false,
      es_despacho_rapido: producto.es_despacho_rapido ?? false,
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const validarFormulario = () => {
    const errores = {};

    if (!formData.bodega) errores.bodega = 'Debe seleccionar una bodega.';

    if (!formData.codigo.trim()) errores.codigo = 'Debe ingresar un código.';
    else if (formData.codigo.length > 30) errores.codigo = 'El código no puede superar 30 caracteres.';

    if (!formData.nombre.trim()) errores.nombre = 'Debe ingresar el nombre del producto.';
    else if (formData.nombre.length > 100) errores.nombre = 'El nombre no puede superar 100 caracteres.';

    if (formData.descripcion.length > 250) {
      errores.descripcion = 'La descripción no puede superar 250 caracteres.';
    }

    if (formData.ubicacion.length > 100) {
      errores.ubicacion = 'La ubicación no puede superar 100 caracteres.';
    }

    const stockActual = Number(formData.stock_actual);
    const stockMinimo = Number(formData.stock_minimo);
    const stockMaximo = Number(formData.stock_maximo);

    if (formData.stock_actual === '' || Number.isNaN(stockActual) || stockActual < 0) {
      errores.stock_actual = 'Stock inicial inválido.';
    }

    if (formData.stock_minimo === '' || Number.isNaN(stockMinimo) || stockMinimo < 0) {
      errores.stock_minimo = 'Stock mínimo inválido.';
    }

    if (formData.stock_maximo === '' || Number.isNaN(stockMaximo) || stockMaximo < 0) {
      errores.stock_maximo = 'Stock máximo inválido.';
    }

    if (!errores.stock_minimo && !errores.stock_maximo && stockMaximo > 0 && stockMinimo > stockMaximo) {
      errores.stock_minimo = 'El mínimo no puede ser mayor al máximo.';
    }

    if (!errores.stock_actual && !errores.stock_maximo && stockMaximo > 0 && stockActual > stockMaximo) {
      errores.stock_actual = 'El stock inicial no puede superar el máximo.';
    }

    setErroresForm(errores);
    return Object.keys(errores).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validarFormulario()) {
      setError('Corrige los campos marcados antes de guardar.');
      return;
    }

    const payload = {
      bodega: formData.bodega,
      codigo: formData.codigo.trim().toUpperCase(),
      nombre: formData.nombre.trim(),
      descripcion: formData.descripcion.trim(),
      marca: '',
      modelo: '',
      unidad_medida: 'Unidad',
      stock_actual: Number(formData.stock_actual || 0),
      stock_minimo: Number(formData.stock_minimo || 0),
      stock_maximo: Number(formData.stock_maximo || 0),
      ubicacion: formData.ubicacion.trim(),
      estado: formData.estado,
      vida_util_dias: formData.vida_util_dias === '' ? null : Number(formData.vida_util_dias),
      es_devolutivo: formData.es_devolutivo,
      es_activo_critico: formData.es_activo_critico,
      es_despacho_rapido: formData.es_despacho_rapido,
    };

    try {
      if (modoEdicion) {
        await api.put(`/inventario/${idEdicion}/`, payload);
      } else {
        await api.post('/inventario/', payload);
      }

      limpiarFormulario();
      cargarDatos();
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === 'object') {
        const backendErrors = {};
        Object.keys(data).forEach((key) => {
          backendErrors[key] = Array.isArray(data[key]) ? data[key][0] : String(data[key]);
        });
        setErroresForm(backendErrors);
      }
      setError('Error al guardar el producto. Verifica los datos.');
    }
  };

  const eliminarProducto = async (id) => {
    if (!window.confirm('¿Desactivar este producto del inventario?')) return;

    try {
      await api.delete(`/inventario/${id}/`);
      cargarDatos();
    } catch {
      setError('No se pudo desactivar el producto.');
    }
  };

  const productosFiltrados = productos.filter((p) => {
    const texto = searchTerm.toLowerCase();

    const coincideTexto =
      p.codigo?.toLowerCase().includes(texto) ||
      p.nombre?.toLowerCase().includes(texto);

    const coincideBodega = filtroBodega
      ? String(p.bodega) === String(filtroBodega)
      : true;

    const coincideReposicion = soloReposicion ? p.necesita_reposicion : true;

    return coincideTexto && coincideBodega && coincideReposicion;
  });

  const totalPaginas = Math.max(1, Math.ceil(productosFiltrados.length / PRODUCTOS_POR_PAGINA));
  const paginaSegura = Math.min(paginaActual, totalPaginas);
  const productosPagina = productosFiltrados.slice(
    (paginaSegura - 1) * PRODUCTOS_POR_PAGINA,
    paginaSegura * PRODUCTOS_POR_PAGINA
  );

  const obtenerEstadoUI = (actual, minimo, maximo) => {
    const act = Number(actual);
    const min = Number(minimo);
    const max = Number(maximo);

    if (act < min) return <span className="badge badge-critico">Crítico</span>;
    if (act === min) return <span className="badge badge-alerta">Alerta Baja</span>;
    if (max > 0 && act > max) return <span className="badge badge-alerta">Sobre Stock</span>;

    return <span className="badge badge-optimo">Óptimo</span>;
  };

  return (
    <div className="inventario-wrapper">
      <h1 className="page-title">Panel Operativo de Bodega</h1>
      <p className="page-subtitle">Gestión real de inventario por bodega</p>

      {error && <div className="error-banner">{error}</div>}

      <div className="action-panel">
        <div className="search-group">
          <span className="search-icon"><FaSearch /></span>
          <input
            type="text"
            placeholder="Buscar por producto o código..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="filter-input"
          />
        </div>

        <div className="search-group">
          <span className="search-icon"><FaMapMarkerAlt /></span>
          <select
            value={filtroBodega}
            onChange={(e) => setFiltroBodega(e.target.value)}
            className="filter-input"
          >
            <option value="">Todas las Bodegas</option>
            {bodegas.map((b) => (
              <option key={b.id} value={b.id}>{b.nombre}</option>
            ))}
          </select>
        </div>

        <label className="toggle-reposicion">
          <input
            type="checkbox"
            checked={soloReposicion}
            onChange={(e) => setSoloReposicion(e.target.checked)}
          />
          Solo necesita reposición
        </label>

        <button className="btn-agregar-main" onClick={abrirCrear}>
          <FaPlus /> Crear Producto
        </button>
      </div>

      {mostrarFormulario && (
        <div className={`form-container ${modoEdicion ? 'edit-mode' : ''}`}>
          <h3>{modoEdicion ? 'Editar Producto de Inventario' : 'Crear Producto en Inventario'}</h3>

          <form onSubmit={handleSubmit} className="form-grid inventario-form-simple">
            <div className="input-group">
              <label>Bodega</label>
              <select name="bodega" value={formData.bodega} onChange={handleChange}>
                <option value="">Seleccione bodega</option>
                {bodegas.map((b) => (
                  <option key={b.id} value={b.id}>{b.nombre}</option>
                ))}
              </select>
              {erroresForm.bodega && <small className="field-error">{erroresForm.bodega}</small>}
            </div>

            <div className="input-group">
              <label>Código interno</label>
              <input
                name="codigo"
                placeholder="Ej: P-001"
                value={formData.codigo}
                onChange={handleChange}
                maxLength="30"
              />
              {erroresForm.codigo && <small className="field-error">{erroresForm.codigo}</small>}
            </div>

            <div className="input-group full-width">
              <label>Nombre del producto</label>
              <input
                name="nombre"
                placeholder="Ej: Buzo de papel"
                value={formData.nombre}
                onChange={handleChange}
                maxLength="100"
              />
              {erroresForm.nombre && <small className="field-error">{erroresForm.nombre}</small>}
            </div>

            <div className="input-group">
              <label>Stock inicial</label>
              <input
                type="number"
                name="stock_actual"
                placeholder="Cantidad disponible"
                value={formData.stock_actual}
                onChange={handleChange}
                min="0"
              />
              {erroresForm.stock_actual && <small className="field-error">{erroresForm.stock_actual}</small>}
            </div>

            <div className="input-group">
              <label>Stock mínimo</label>
              <input
                type="number"
                name="stock_minimo"
                placeholder="Alerta bajo este número"
                value={formData.stock_minimo}
                onChange={handleChange}
                min="0"
              />
              {erroresForm.stock_minimo && <small className="field-error">{erroresForm.stock_minimo}</small>}
            </div>

            <div className="input-group">
              <label>Stock máximo</label>
              <input
                type="number"
                name="stock_maximo"
                placeholder="Capacidad máxima"
                value={formData.stock_maximo}
                onChange={handleChange}
                min="0"
              />
              {erroresForm.stock_maximo && <small className="field-error">{erroresForm.stock_maximo}</small>}
            </div>

            <div className="input-group">
              <label>Ubicación interna</label>
              <input
                name="ubicacion"
                placeholder="Ej: Estante A-3"
                value={formData.ubicacion}
                onChange={handleChange}
                maxLength="100"
              />
              {erroresForm.ubicacion && <small className="field-error">{erroresForm.ubicacion}</small>}
            </div>

            <div className="input-group">
              <label>Vida útil (días)</label>
              <input
                type="number"
                name="vida_util_dias"
                placeholder="Ej: 365 (cascos, zapatos). Vacío = sin control"
                value={formData.vida_util_dias}
                onChange={handleChange}
                min="1"
              />
              {erroresForm.vida_util_dias && <small className="field-error">{erroresForm.vida_util_dias}</small>}
            </div>

            <div className="input-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="es_devolutivo"
                  checked={formData.es_devolutivo}
                  onChange={handleChange}
                />
                {' '}Es un activo devolutivo (ej. radios)
              </label>
            </div>

            <div className="input-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="es_activo_critico"
                  checked={formData.es_activo_critico}
                  onChange={handleChange}
                />
                {' '}Activo crítico / alto valor (exige firma de supervisor ante faltantes en auditoría)
              </label>
            </div>

            <div className="input-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="es_despacho_rapido"
                  checked={formData.es_despacho_rapido}
                  onChange={handleChange}
                />
                {' '}Despacho rápido (ej. agua: sin RUT ni firma, un clic)
              </label>
            </div>

            <div className="input-group full-width">
              <label>Descripción opcional</label>
              <textarea
                name="descripcion"
                placeholder="Detalle breve del producto"
                value={formData.descripcion}
                onChange={handleChange}
                maxLength="250"
              />
              {erroresForm.descripcion && <small className="field-error">{erroresForm.descripcion}</small>}
            </div>

            <div className="form-actions full-width">
              <button type="submit" className="btn-guardar">
                {modoEdicion ? 'Actualizar Producto' : 'Guardar Producto'}
              </button>

              <button type="button" onClick={limpiarFormulario} className="btn-cancelar">
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="table-section">
        <div className="table-header-dark">
          <FaFilter style={{ color: '#ea580c', marginRight: '10px' }} />
          ESTADO FÍSICO DEL INVENTARIO ({productosFiltrados.length} Registros)
        </div>

        <div className="table-responsive">
          <table className="styled-table">
            <thead>
              <tr>
                <th>ÍTEM / CÓDIGO</th>
                <th>BODEGA</th>
                <th className="text-center">STOCK</th>
                <th className="text-center">MÍN.</th>
                <th className="text-center">MÁX.</th>
                <th className="text-center">ESTADO</th>
                <th className="text-center">ACCIONES</th>
              </tr>
            </thead>

            <tbody>
              {productosPagina.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center empty-state">
                    No se encontraron productos en esta ubicación.
                  </td>
                </tr>
              ) : (
                productosPagina.map((prod) => (
                  <tr key={prod.id}>
                    <td>
                      <div className="item-title">{prod.nombre}</div>
                      <div className="item-subtitle">{prod.codigo}</div>

                      {(prod.es_devolutivo || prod.vida_util_dias || prod.es_activo_critico || prod.es_despacho_rapido) && (
                        <div className="item-tags">
                          {prod.es_devolutivo && (
                            <span className="tag-devolutivo"><FaSyncAlt /> Devolutivo</span>
                          )}
                          {prod.vida_util_dias && (
                            <span className="tag-vencimiento"><FaHourglassHalf /> Vida útil: {prod.vida_util_dias}d</span>
                          )}
                          {prod.es_activo_critico && (
                            <span className="tag-critico"><FaExclamationTriangle /> Alto valor</span>
                          )}
                          {prod.es_despacho_rapido && (
                            <span className="tag-despacho"><FaBolt /> Despacho rápido</span>
                          )}
                        </div>
                      )}
                    </td>

                    <td>{prod.bodega_nombre || 'Sin bodega'}</td>
                    <td className="text-center stock-number highlight-stock">{prod.stock_actual}</td>
                    <td className="text-center stock-number min-stock">{prod.stock_minimo}</td>
                    <td className="text-center stock-number">{prod.stock_maximo}</td>
                    <td className="text-center">
                      {obtenerEstadoUI(prod.stock_actual, prod.stock_minimo, prod.stock_maximo)}
                    </td>

                    <td className="text-center">
                      <div className="action-buttons">
                        {prod.es_devolutivo && (
                          <button
                            className="btn-icon btn-unidades"
                            title="Gestionar unidades individuales"
                            onClick={() => abrirPanelUnidades(prod)}
                          >
                            <FaBarcode />
                          </button>
                        )}

                        <button className="btn-icon btn-edit" onClick={() => cargarParaEdicion(prod)}>
                          <FaEdit />
                        </button>

                        <button className="btn-icon btn-delete" onClick={() => eliminarProducto(prod.id)}>
                          <FaTrashAlt />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalPaginas > 1 && (
          <div className="paginacion">
            <button
              className="btn-paginacion"
              onClick={() => setPaginaActual((p) => Math.max(1, p - 1))}
              disabled={paginaSegura === 1}
            >
              <FaChevronLeft /> Anterior
            </button>

            <span className="paginacion-info">Página {paginaSegura} de {totalPaginas}</span>

            <button
              className="btn-paginacion"
              onClick={() => setPaginaActual((p) => Math.min(totalPaginas, p + 1))}
              disabled={paginaSegura === totalPaginas}
            >
              Siguiente <FaChevronRight />
            </button>
          </div>
        )}
      </div>

      <div className="table-section">
        <div className="table-header-dark">
          <FaExclamationTriangle style={{ color: '#f59e0b', marginRight: '10px' }} />
          ÚLTIMOS MOVIMIENTOS DETECTADOS

          <button className="btn-ver-todos" onClick={() => navigate('/movimientos')}>
            Ver todos <FaExternalLinkAlt />
          </button>
        </div>

        <div className="table-responsive">
          <table className="styled-table">
            <thead>
              <tr className="light-header">
                <th>FECHA Y HORA</th>
                <th>TIPO DE MOVIMIENTO</th>
                <th>RESPONSABLE</th>
              </tr>
            </thead>

            <tbody>
              {movimientos.length === 0 ? (
                <tr>
                  <td colSpan="3" className="text-center empty-state">
                    Aún no hay movimientos registrados.
                  </td>
                </tr>
              ) : (
                movimientos.slice(0, 5).map((mov) => (
                  <tr key={mov.id}>
                    <td>{new Date(mov.fecha).toLocaleString()}</td>
                    <td>
                      <strong>{mov.tipo_movimiento}</strong>: {mov.cantidad} unidades
                    </td>
                    <td>{mov.usuario_nombre || 'Sistema Automático'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {productoUnidades && (
        <div className="unidades-modal-overlay" onClick={cerrarPanelUnidades}>
          <div className="unidades-modal" onClick={(e) => e.stopPropagation()}>
            <div className="unidades-modal-header">
              <div>
                <h3>Unidades de {productoUnidades.nombre}</h3>
                <p>Cada unidad representa un equipo físico individual (ej. RADIO-S001).</p>
              </div>

              <button className="btn-cerrar-modal" onClick={cerrarPanelUnidades}>
                <FaTimes />
              </button>
            </div>

            {errorUnidades && <div className="error-banner">{errorUnidades}</div>}

            <div className="unidades-form-row">
              <input
                type="text"
                placeholder="Código de unidad (ej. RADIO-S001)"
                value={nuevoCodigoUnidad}
                onChange={(e) => setNuevoCodigoUnidad(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && agregarUnidad()}
              />

              <button className="btn-agregar-unidad" onClick={agregarUnidad}>
                <FaPlus /> Agregar
              </button>
            </div>

            <div className="unidades-lista">
              {unidades.length === 0 ? (
                <div className="text-center empty-state">Aún no hay unidades registradas.</div>
              ) : (
                unidades.map((u) => (
                  <div key={u.id} className={`unidad-item unidad-${u.estado.toLowerCase()}`}>
                    <span className="unidad-codigo">{u.codigo}</span>
                    <span className="unidad-estado">{u.estado}</span>

                    {u.estado === 'EN_MANTENCION' && (
                      <button
                        className="btn-reparar-unidad"
                        title="Marcar como reparada"
                        onClick={() => repararUnidad(u)}
                      >
                        <FaTools /> Reparada
                      </button>
                    )}

                    {(u.estado === 'DISPONIBLE' || u.estado === 'EN_MANTENCION') && (
                      <button
                        className="btn-baja-unidad"
                        title="Dar de baja"
                        onClick={() => darDeBajaUnidad(u)}
                      >
                        <FaBan />
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Inventario;