import { useState, useEffect } from 'react';
import {
  FaExclamationTriangle,
  FaFileExcel,
  FaChartLine,
  FaShoppingCart,
  FaUserSecret,
  FaSearch,
  FaCoins,
  FaBoxes,
  FaSyncAlt,
  FaInfoCircle,
  FaCheckCircle,
} from 'react-icons/fa';

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

import { Line } from 'react-chartjs-2';
import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import './DashboardGerencial.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const UMBRAL_RIESGO_ALTO = 70;
const UMBRAL_RIESGO_MEDIO = 40;

const formatearCLP = (valor) =>
  Number(valor || 0).toLocaleString('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });

// El backend manda fechas sin hora ("2026-11-02"). new Date() las toma como
// medianoche UTC, y en Chile (UTC-3) eso cae el día anterior: el panel
// mostraba un día menos de plazo para pedir. Se arma como fecha local.
const formatearFecha = (iso) => {
  const [anio, mes, dia] = String(iso).split('-').map(Number);
  return new Date(anio, mes - 1, dia).toLocaleDateString('es-CL');
};

// Urgencia en palabras en vez de un porcentaje: quien lee el panel no
// necesita interpretar "73% de probabilidad de quiebre" para saber qué hacer.
const textoUrgencia = (probabilidad) => {
  if (probabilidad >= UMBRAL_RIESGO_ALTO) return { texto: 'Urgente', clase: 'pg-pill-rojo' };
  if (probabilidad >= UMBRAL_RIESGO_MEDIO) return { texto: 'Pronto', clase: 'pg-pill-ambar' };
  return { texto: 'Planificar', clase: 'pg-pill-azul' };
};

const iniciales = (nombre) =>
  String(nombre || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0].toUpperCase())
    .join('');

const NotaCalculo = ({ children }) => (
  <p className="pg-nota"><FaInfoCircle /> {children}</p>
);

const Vacio = ({ children }) => (
  <div className="pg-vacio"><FaCheckCircle /> {children}</div>
);

const pluralizar = (cantidad, singular, plural) => `${cantidad} ${cantidad === 1 ? singular : plural}`;

const DashboardGerencial = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actualizadoEn, setActualizadoEn] = useState(null);

  const [prediccionSemanal, setPrediccionSemanal] = useState({
    historico: { labels: [], data: [] },
    proyeccion_proxima_semana: 0,
    confiable: false,
  });
  const [prediccionProducto, setPrediccionProducto] = useState([]);
  const [presupuestoProyectado, setPresupuestoProyectado] = useState({ semanal_clp: 0, mensual_clp: 0 });
  const [quiebreStock, setQuiebreStock] = useState([]);
  const [recomendaciones, setRecomendaciones] = useState([]);
  const [anomalias, setAnomalias] = useState([]);
  const [capitalInmovilizado, setCapitalInmovilizado] = useState({ items: [], total_clp: 0, cantidad_items: 0 });

  const [resumenAbc, setResumenAbc] = useState({});
  const [abcConfiable, setAbcConfiable] = useState(false);
  const [abcMotivo, setAbcMotivo] = useState('');

  const [busqueda, setBusqueda] = useState('');
  const [busquedaResultado, setBusquedaResultado] = useState(null);
  const [busquedaLoading, setBusquedaLoading] = useState(false);
  const [busquedaError, setBusquedaError] = useState('');

  useEffect(() => {
    cargarDashboard();
  }, []);

  const cargarDashboard = async () => {
    try {
      setLoading(true);
      setError('');

      const [resumenRes, mlAvanzadoRes] = await Promise.allSettled([
        api.get('/dashboard/resumen/'),
        api.get('/dashboard/ml-avanzado/'),
      ]);

      if (resumenRes.status === 'fulfilled') {
        const data = resumenRes.value.data || {};

        setPrediccionSemanal({
          historico: data.prediccion_consumo?.historico || { labels: [], data: [] },
          proyeccion_proxima_semana: Number(data.prediccion_consumo?.proyeccion_proxima_semana || 0),
          confiable: Boolean(data.prediccion_consumo?.confiable),
        });
        setPrediccionProducto(Array.isArray(data.prediccion_consumo_producto) ? data.prediccion_consumo_producto : []);
        setPresupuestoProyectado(data.presupuesto_proyectado || { semanal_clp: 0, mensual_clp: 0 });
        setQuiebreStock(Array.isArray(data.quiebre_stock) ? data.quiebre_stock : []);
        setRecomendaciones(Array.isArray(data.recomendaciones_reposicion) ? data.recomendaciones_reposicion : []);
        setAnomalias(Array.isArray(data.anomalias_consumo) ? data.anomalias_consumo : []);
        setCapitalInmovilizado(data.capital_inmovilizado || { items: [], total_clp: 0, cantidad_items: 0 });
      } else {
        console.error(resumenRes.reason);
        setError('No se pudo cargar el Panel Gerencial. Intenta recargar la página.');
      }

      if (mlAvanzadoRes.status === 'fulfilled') {
        const data = mlAvanzadoRes.value.data || {};

        const abc = data.clasificacion_abc || {};
        setResumenAbc(abc.resumen || {});
        setAbcConfiable(Boolean(abc.confiable));
        setAbcMotivo(abc.motivo || '');
      } else {
        console.error(mlAvanzadoRes.reason);
        setResumenAbc({});
        setAbcConfiable(false);
        setAbcMotivo('No se pudo cargar la clasificación ABC de inventario.');
      }
    } finally {
      setActualizadoEn(new Date());
      setLoading(false);
    }
  };

  const ejecutarBusqueda = async (e) => {
    e.preventDefault();
    const consulta = busqueda.trim();
    if (!consulta) return;

    try {
      setBusquedaLoading(true);
      setBusquedaError('');

      const response = await api.get('/dashboard/ml-busqueda/', { params: { q: consulta } });
      setBusquedaResultado(response.data);
    } catch (err) {
      console.error(err);
      setBusquedaResultado(null);
      setBusquedaError('No se pudo ejecutar la búsqueda. Intenta nuevamente.');
    } finally {
      setBusquedaLoading(false);
    }
  };

  const exportarDashboardExcel = async () => {
    const workbook = new ExcelJS.Workbook();
    workbook.creator = 'NexoFaena SGI';
    workbook.created = new Date();

    const estiloTitulo = (cell, texto, color = 'FF0F2647') => {
      cell.value = texto;
      cell.font = { bold: true, size: 14, color: { argb: 'FFFFFFFF' } };
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: color } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
    };

    const estiloHeader = (row) => {
      row.eachCell((cell) => {
        cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1F6FD1' } };
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
      });
    };

    const resumen = workbook.addWorksheet('Resumen IA');
    resumen.mergeCells('A1:D1');
    estiloTitulo(resumen.getCell('A1'), 'NEXOFAENA SGI - PANEL GERENCIAL');
    resumen.getRow(1).height = 28;
    resumen.columns = [{ width: 34 }, { width: 22 }, { width: 22 }, { width: 22 }];
    resumen.addRow([]);
    resumen.addRow(['Generado', new Date().toLocaleString()]);
    resumen.addRow(['Proyección próxima semana (Regresión Lineal)', `${prediccionSemanal.proyeccion_proxima_semana} unidades`]);
    resumen.addRow(['Productos con riesgo de quiebre (Regresión Logística)', quiebreStock.length]);
    resumen.addRow(['Recomendaciones de reposición activas', recomendaciones.length]);
    resumen.addRow(['Anomalías de consumo detectadas (K-Means)', anomalias.length]);

    const planificacion = workbook.addWorksheet('Planificación y Compras');
    planificacion.columns = [
      { header: 'Producto', key: 'producto', width: 32 },
      { header: 'Bodega', key: 'bodega', width: 24 },
      { header: 'Proyección semana', key: 'semana', width: 18 },
      { header: 'Proyección mes', key: 'mes', width: 18 },
      { header: 'Algoritmo', key: 'algoritmo', width: 20 },
    ];
    estiloHeader(planificacion.getRow(1));
    prediccionProducto.forEach((p) => {
      planificacion.addRow({
        producto: p.producto_nombre,
        bodega: p.bodega_nombre,
        semana: p.proyeccion_semana,
        mes: p.proyeccion_mes,
        algoritmo: p.algoritmo,
      });
    });

    const prevencion = workbook.addWorksheet('Prevención Operativa');
    prevencion.columns = [
      { header: 'Producto', key: 'producto', width: 30 },
      { header: 'Bodega', key: 'bodega', width: 22 },
      { header: 'Stock actual', key: 'stock', width: 14 },
      { header: 'Días restantes', key: 'dias', width: 16 },
      { header: 'Tiempo reposición (días)', key: 'reposicion', width: 20 },
      { header: 'Probabilidad de quiebre', key: 'prob', width: 20 },
    ];
    estiloHeader(prevencion.getRow(1));
    quiebreStock.forEach((q) => {
      prevencion.addRow({
        producto: q.producto_nombre,
        bodega: q.bodega_nombre,
        stock: q.stock_actual,
        dias: q.dias_restantes_estimados,
        reposicion: q.tiempo_reposicion_dias,
        prob: `${q.probabilidad_quiebre}%`,
      });
    });

    prevencion.addRow([]);
    const headerReco = prevencion.addRow(['Recomendaciones de reposición']);
    headerReco.getCell(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
    headerReco.getCell(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF0F2647' } };
    const headerReco2 = prevencion.addRow(['Producto', 'Bodega', 'Pedir antes de', 'Cantidad sugerida', 'Riesgo']);
    estiloHeader(headerReco2);
    recomendaciones.forEach((r) => {
      prevencion.addRow([
        r.producto_nombre,
        r.bodega_nombre,
        formatearFecha(r.fecha_sugerida_pedido),
        r.cantidad_sugerida,
        `${r.probabilidad_quiebre}%`,
      ]);
    });

    const auditoria = workbook.addWorksheet('Auditoría Robo Hormiga');
    auditoria.columns = [
      { header: 'Trabajador', key: 'trabajador', width: 28 },
      { header: 'Producto destacado', key: 'producto', width: 26 },
      { header: 'Bodega', key: 'bodega', width: 22 },
      { header: 'Total mes', key: 'total', width: 14 },
      { header: 'N° entregas', key: 'entregas', width: 14 },
      { header: 'Algoritmo', key: 'algoritmo', width: 20 },
      { header: 'Mensaje', key: 'mensaje', width: 60 },
    ];
    estiloHeader(auditoria.getRow(1));
    anomalias.forEach((a) => {
      auditoria.addRow({
        trabajador: a.trabajador_nombre,
        producto: a.producto_nombre,
        bodega: a.bodega_nombre,
        total: a.cantidad_mes,
        entregas: a.num_entregas,
        algoritmo: a.algoritmo,
        mensaje: a.mensaje,
      });
    });

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    saveAs(blob, `NexoFaena_Modelo_IA_${Date.now()}.xlsx`);
  };

  ChartJS.defaults.color = '#9aabc4';
  ChartJS.defaults.font.family = "'Inter', sans-serif";

  const historico = prediccionSemanal.historico.data;
  const ultimoReal = historico.length ? historico[historico.length - 1] : null;

  const chartDataHistorico = {
    labels: [...prediccionSemanal.historico.labels, 'Próx.'],
    datasets: [
      {
        label: 'Entregadas',
        data: [...historico, null],
        borderColor: '#3d8ff0',
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 5,
        fill: true,
        tension: 0.35,
        backgroundColor: (contexto) => {
          const { ctx, chartArea } = contexto.chart;
          if (!chartArea) return 'rgba(61, 143, 240, 0.15)';
          const degradado = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          degradado.addColorStop(0, 'rgba(61, 143, 240, 0.32)');
          degradado.addColorStop(1, 'rgba(61, 143, 240, 0)');
          return degradado;
        },
      },
      {
        // Tramo punteado desde la última semana real hasta lo estimado.
        label: 'Estimado',
        data: [...historico.map((_, i) => (i === historico.length - 1 ? ultimoReal : null)), prediccionSemanal.proyeccion_proxima_semana],
        borderColor: '#22d3ee',
        borderWidth: 2,
        borderDash: [6, 6],
        pointRadius: (contexto) => (contexto.dataIndex === historico.length ? 5 : 0),
        pointBackgroundColor: '#22d3ee',
        fill: false,
      },
    ],
  };

  const chartOptionsConsumo = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#0f2647',
        borderColor: 'rgba(91, 178, 255, 0.25)',
        borderWidth: 1,
        padding: 10,
        displayColors: false,
        filter: (item) => item.raw !== null && !(item.datasetIndex === 1 && item.dataIndex < historico.length),
        callbacks: { label: (item) => `${item.dataset.label}: ${item.formattedValue} unidades` },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        border: { display: false },
        grid: { color: 'rgba(255, 255, 255, 0.06)' },
        ticks: { maxTicksLimit: 5 },
      },
      x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 12 } },
    },
  };

  const productosPorAgotarse = quiebreStock.filter((q) => q.probabilidad_quiebre >= UMBRAL_RIESGO_ALTO).length;

  const masConsumidos = [...prediccionProducto]
    .sort((a, b) => b.proyeccion_mes - a.proyeccion_mes)
    .slice(0, 3);

  const valorTotalAbc = ['A', 'B', 'C'].reduce((total, clase) => total + Number(resumenAbc[clase]?.valor_stock_clp || 0), 0);

  // Cuatro cifras que responden "¿cómo estamos?" de un vistazo. El estado
  // (requiere acción / revisar / en orden) se decide acá para que la persona
  // no tenga que interpretar el número.
  const indicadores = [
    {
      titulo: 'Productos por agotarse',
      valor: productosPorAgotarse,
      ayuda: 'con alto riesgo de quedarse sin stock',
      estado: productosPorAgotarse > 0 ? 'rojo' : 'verde',
      Icono: FaExclamationTriangle,
    },
    {
      titulo: 'Gasto estimado del mes',
      valor: formatearCLP(presupuestoProyectado.mensual_clp),
      ayuda: 'para reponer lo que se va a consumir',
      estado: 'azul',
      Icono: FaCoins,
    },
    {
      titulo: 'Consumos fuera de lo normal',
      valor: anomalias.length,
      ayuda: anomalias.length === 1 ? 'trabajador a revisar este mes' : 'trabajadores a revisar este mes',
      estado: anomalias.length > 0 ? 'ambar' : 'verde',
      Icono: FaUserSecret,
    },
    {
      titulo: 'Dinero detenido en bodega',
      valor: formatearCLP(capitalInmovilizado.total_clp),
      ayuda: 'en productos con stock para más de 6 meses',
      estado: capitalInmovilizado.total_clp > 0 ? 'ambar' : 'verde',
      Icono: FaBoxes,
    },
  ];

  const ETIQUETA_ESTADO = { rojo: 'Requiere acción', ambar: 'Revisar', verde: 'En orden', azul: 'Proyección' };

  return (
    <div className="pg">
      <header className="pg-encabezado">
        <div>
          <h1 className="pg-titulo">Panel Gerencial</h1>
          <p className="pg-subtitulo">
            Lo más importante de la bodega, explicado en simple.
            {actualizadoEn && (
              <span className="pg-actualizado">
                {' '}Actualizado a las {actualizadoEn.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}.
              </span>
            )}
          </p>
        </div>

        <div className="pg-acciones">
          <button type="button" className="pg-boton" onClick={cargarDashboard} disabled={loading}>
            <FaSyncAlt className={loading ? 'pg-girando' : ''} /> Actualizar
          </button>
          <button type="button" className="pg-boton pg-boton-primario" onClick={exportarDashboardExcel} disabled={loading}>
            <FaFileExcel /> Exportar Excel
          </button>
        </div>
      </header>

      {error && <div className="pg-aviso pg-aviso-error"><FaExclamationTriangle /> {error}</div>}

      {/* ============ RESUMEN ============ */}
      <div className="pg-indicadores">
        {indicadores.map(({ titulo, valor, ayuda, estado, Icono }) => (
          <div key={titulo} className="pg-indicador">
            <div className="pg-indicador-cabecera">
              <span className={`pg-icono pg-icono-${estado}`}><Icono /></span>
              <span className={`pg-pill pg-pill-${estado}`}>{ETIQUETA_ESTADO[estado]}</span>
            </div>
            <div className="pg-indicador-titulo">{titulo}</div>
            <div className="pg-indicador-valor">{loading ? <span className="pg-esqueleto" /> : valor}</div>
            <div className="pg-indicador-ayuda">{ayuda}</div>
          </div>
        ))}
      </div>

      {/* ============ BUSCADOR ============ */}
      <form className="pg-buscador" onSubmit={ejecutarBusqueda}>
        <FaSearch className="pg-buscador-icono" />
        <input
          type="text"
          className="pg-buscador-input"
          placeholder="Busca un producto (cascos, guantes…)"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
        <button
          type="submit"
          className="pg-boton pg-boton-primario pg-buscador-boton"
          disabled={busquedaLoading || !busqueda.trim()}
          aria-label="Buscar"
        >
          <FaSearch className="pg-solo-movil" />
          <span className="pg-solo-escritorio">{busquedaLoading ? 'Buscando…' : 'Buscar'}</span>
        </button>
      </form>

      {busquedaError && <div className="pg-aviso pg-aviso-error"><FaExclamationTriangle /> {busquedaError}</div>}

      {busquedaResultado && !busquedaError && (
        <div className="pg-resultados">
          {!busquedaResultado.confiable || (busquedaResultado.resultados || []).length === 0 ? (
            <div className="pg-aviso"><FaInfoCircle /> {busquedaResultado.motivo || 'Sin resultados para esa búsqueda.'}</div>
          ) : (
            busquedaResultado.resultados.map((r) => (
              <div key={r.inventario_id} className="pg-resultado">
                <div className="pg-resultado-nombre">
                  {r.producto_nombre}
                  {r.necesita_reposicion && <span className="pg-pill pg-pill-ambar">Bajo el mínimo</span>}
                </div>
                <div className="pg-resultado-datos">
                  <span><strong className="pg-num">{r.stock_actual}</strong> en stock</span>
                  <span><strong className="pg-num">{r.consumo_mensual_estimado}</strong> al mes</span>
                  <span>{r.bodega_nombre}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ============ ¿QUÉ HAY QUE COMPRAR? ============ */}
      <section className="pg-seccion">
        <div className="pg-seccion-cabecera">
          <div>
            <h2><FaShoppingCart /> ¿Qué hay que comprar?</h2>
            <p>Productos que conviene pedir ahora para no quedarse sin stock en faena.</p>
          </div>
          {recomendaciones.length > 0 && (
            <span className="pg-contador">{pluralizar(recomendaciones.length, 'producto', 'productos')}</span>
          )}
        </div>

        {recomendaciones.length === 0 ? (
          <Vacio>Todo en orden: no hay que comprar nada por ahora.</Vacio>
        ) : (
          <>
          {/* En celular, cada compra en dos líneas en vez de una tarjeta de 5 filas. */}
          <ul className="pg-lista pg-solo-movil">
            {recomendaciones.slice(0, 8).map((r) => {
              const urgencia = textoUrgencia(r.probabilidad_quiebre);
              return (
                <li key={r.inventario_id} className="pg-lista-item">
                  <div className="pg-lista-linea">
                    <span className="pg-fuerte">{r.producto_nombre}</span>
                    <span className={`pg-pill ${urgencia.clase}`}><span className="pg-punto" />{urgencia.texto}</span>
                  </div>
                  <div className="pg-lista-detalle">
                    Pedir <strong className="pg-num">{r.cantidad_sugerida} un.</strong> antes del{' '}
                    <strong className="pg-num">{formatearFecha(r.fecha_sugerida_pedido)}</strong> · {r.bodega_nombre}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="pg-tabla-contenedor pg-solo-escritorio">
            <table className="pg-tabla">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Bodega</th>
                  <th>Pedir antes del</th>
                  <th className="pg-der">Cantidad</th>
                  <th className="pg-der">Urgencia</th>
                </tr>
              </thead>
              <tbody>
                {recomendaciones.slice(0, 8).map((r) => {
                  const urgencia = textoUrgencia(r.probabilidad_quiebre);
                  return (
                    <tr key={r.inventario_id}>
                      <td className="pg-fuerte" data-label="Producto">{r.producto_nombre}</td>
                      <td className="pg-suave" data-label="Bodega">{r.bodega_nombre}</td>
                      <td className="pg-num" data-label="Pedir antes del">{formatearFecha(r.fecha_sugerida_pedido)}</td>
                      <td className="pg-num pg-der" data-label="Cantidad">{r.cantidad_sugerida} un.</td>
                      <td className="pg-der" data-label="Urgencia">
                        <span className={`pg-pill ${urgencia.clase}`}><span className="pg-punto" />{urgencia.texto}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          </>
        )}

        <NotaCalculo>Regresión Logística con los días de stock disponibles y el tiempo de entrega del proveedor.</NotaCalculo>
      </section>

      <div className="pg-dos-columnas">
        {/* ============ ¿CUÁNTO SE VA A CONSUMIR? ============ */}
        <section className="pg-seccion">
          <div className="pg-seccion-cabecera">
            <div>
              <h2><FaChartLine /> ¿Cuánto se va a consumir?</h2>
              <p>
                La próxima semana se esperan unas{' '}
                <strong className="pg-num">{prediccionSemanal.proyeccion_proxima_semana}</strong> unidades
                {!prediccionSemanal.confiable && ' (estimación preliminar)'}.
              </p>
            </div>
          </div>

          <div className="pg-grafico">
            {historico.length === 0 ? (
              <Vacio>Todavía no hay entregas suficientes para graficar.</Vacio>
            ) : (
              <Line data={chartDataHistorico} options={chartOptionsConsumo} />
            )}
          </div>

          {masConsumidos.length > 0 && (
            <ul className="pg-ranking">
              {masConsumidos.map((p, i) => (
                <li key={p.inventario_id}>
                  <span className="pg-ranking-pos">{i + 1}</span>
                  <span className="pg-ranking-nombre">{p.producto_nombre}</span>
                  <span className="pg-num pg-suave">{p.proyeccion_mes} / mes</span>
                </li>
              ))}
            </ul>
          )}

          <NotaCalculo>Regresión Lineal y Random Forest sobre las últimas 12 semanas.</NotaCalculo>
        </section>

        {/* ============ ¿HAY CONSUMOS FUERA DE LO NORMAL? ============ */}
        <section className="pg-seccion">
          <div className="pg-seccion-cabecera">
            <div>
              <h2><FaUserSecret /> ¿Hay consumos fuera de lo normal?</h2>
              <p>Quienes retiraron bastante más que otros de su mismo cargo. Es una señal para revisar, no una acusación.</p>
            </div>
            {anomalias.length > 0 && (
              <span className="pg-contador pg-contador-ambar">{pluralizar(anomalias.length, 'trabajador', 'trabajadores')}</span>
            )}
          </div>

          {anomalias.length === 0 ? (
            <Vacio>Todo en orden: nadie se sale del consumo habitual este mes.</Vacio>
          ) : (
            <ul className="pg-personas">
              {anomalias.map((a) => (
                <li key={`${a.trabajador_id}-${a.inventario_id}`} className="pg-persona">
                  <span className="pg-avatar">{iniciales(a.trabajador_nombre)}</span>
                  <div className="pg-persona-cuerpo">
                    <div className="pg-persona-nombre">
                      {a.trabajador_nombre}
                      {a.cargo && <span className="pg-suave"> · {a.cargo}</span>}
                    </div>
                    <div className="pg-persona-detalle">
                      <strong className="pg-num">{Math.round(a.cantidad_mes)}</strong> unidades este mes,
                      sobre todo <strong>{a.producto_nombre}</strong>.
                    </div>
                  </div>
                  {a.impacto_financiero_clp > 0 && (
                    <span className="pg-monto" title="Costo del consumo por sobre lo esperado">
                      {formatearCLP(a.impacto_financiero_clp)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}

          <NotaCalculo>K-Means agrupa a los trabajadores de cada cargo por su patrón de consumo.</NotaCalculo>
        </section>
      </div>

      {/* ============ ¿DÓNDE ESTÁ EL DINERO? ============ */}
      <section className="pg-seccion">
        <div className="pg-seccion-cabecera">
          <div>
            <h2><FaCoins /> ¿Dónde está el dinero?</h2>
            <p>Cuánto vale lo que hay en bodega y qué productos tienen más stock del necesario.</p>
          </div>
          {valorTotalAbc > 0 && <span className="pg-contador">{formatearCLP(valorTotalAbc)} en total</span>}
        </div>

        {!abcConfiable && abcMotivo && <div className="pg-aviso"><FaInfoCircle /> {abcMotivo}</div>}

        <div className="pg-niveles">
          {[
            { clase: 'A', nombre: 'Alto valor', detalle: 'control estricto', color: 'rojo' },
            { clase: 'B', nombre: 'Valor medio', detalle: 'control normal', color: 'ambar' },
            { clase: 'C', nombre: 'Consumo masivo', detalle: 'despacho ágil', color: 'verde' },
          ].map(({ clase, nombre, detalle, color }) => {
            const valor = Number(resumenAbc[clase]?.valor_stock_clp || 0);
            const porcentaje = valorTotalAbc > 0 ? Math.round((valor / valorTotalAbc) * 100) : 0;
            return (
              <div key={clase} className="pg-nivel">
                <div className="pg-nivel-cabecera">
                  <span className="pg-nivel-nombre">{nombre}</span>
                  <span className="pg-num pg-suave">{porcentaje}%</span>
                </div>
                <div className="pg-nivel-valor pg-num">{formatearCLP(valor)}</div>
                <div className="pg-barra"><span className={`pg-barra-relleno pg-fondo-${color}`} style={{ width: `${porcentaje}%` }} /></div>
                <div className="pg-nivel-detalle">{pluralizar(resumenAbc[clase]?.cantidad || 0, 'producto', 'productos')} · {detalle}</div>
              </div>
            );
          })}
        </div>

        <h3 className="pg-subtitulo-seccion"><FaBoxes /> Exceso de stock <span className="pg-suave">· se podría mover a otra faena o pausar su compra</span></h3>

        {capitalInmovilizado.items.length === 0 ? (
          <Vacio>Sin exceso de stock.</Vacio>
        ) : (
          <>
          <ul className="pg-lista pg-solo-movil">
            {capitalInmovilizado.items.slice(0, 6).map((c) => (
              <li key={c.inventario_id} className="pg-lista-item">
                <div className="pg-lista-linea">
                  <span className="pg-fuerte">{c.producto_nombre}</span>
                  <span className="pg-num pg-fuerte">{formatearCLP(c.capital_inmovilizado_clp)}</span>
                </div>
                <div className="pg-lista-detalle">
                  {c.dias_cobertura_estimados
                    ? <>Alcanza para <strong className="pg-num">{Math.round(c.dias_cobertura_estimados / 30)} meses</strong></>
                    : 'Sin consumo reciente'}
                  {' · '}{c.bodega_nombre}
                </div>
              </li>
            ))}
          </ul>
          <div className="pg-tabla-contenedor pg-solo-escritorio">
            <table className="pg-tabla">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Bodega</th>
                  <th className="pg-der">Alcanza para</th>
                  <th className="pg-der">Dinero detenido</th>
                </tr>
              </thead>
              <tbody>
                {capitalInmovilizado.items.slice(0, 6).map((c) => (
                  <tr key={c.inventario_id}>
                    <td className="pg-fuerte" data-label="Producto">{c.producto_nombre}</td>
                    <td className="pg-suave" data-label="Bodega">{c.bodega_nombre}</td>
                    <td className="pg-num pg-der" data-label="Alcanza para">
                      {c.dias_cobertura_estimados ? `${Math.round(c.dias_cobertura_estimados / 30)} meses` : 'Sin consumo reciente'}
                    </td>
                    <td className="pg-num pg-der pg-fuerte" data-label="Dinero detenido">{formatearCLP(c.capital_inmovilizado_clp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}

        <NotaCalculo>K-Means clasifica el catálogo por precio y rotación (clasificación ABC).</NotaCalculo>
      </section>
    </div>
  );
};

export default DashboardGerencial;
