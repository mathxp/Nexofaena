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
  if (probabilidad >= UMBRAL_RIESGO_ALTO) return { texto: 'Urgente', clase: 'riesgo-alto' };
  if (probabilidad >= UMBRAL_RIESGO_MEDIO) return { texto: 'Pronto', clase: 'riesgo-medio' };
  return { texto: 'Planificar', clase: 'riesgo-bajo' };
};

const DashboardGerencial = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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

  const chartDataHistorico = {
    labels: [...prediccionSemanal.historico.labels, 'Próxima semana'],
    datasets: [
      {
        label: 'Unidades entregadas',
        data: [...prediccionSemanal.historico.data, null],
        borderColor: '#3d8ff0',
        backgroundColor: 'rgba(61, 143, 240, 0.15)',
        fill: true,
        tension: 0.35,
      },
      {
        label: 'Estimado próxima semana',
        data: [
          ...prediccionSemanal.historico.data.map(() => null),
          prediccionSemanal.proyeccion_proxima_semana,
        ],
        borderColor: '#22d3ee',
        backgroundColor: '#22d3ee',
        pointRadius: 7,
        showLine: false,
      },
    ],
  };

  const chartOptionsConsumo = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.08)' } },
      x: { grid: { display: false } },
    },
  };

  const productosPorAgotarse = quiebreStock.filter((q) => q.probabilidad_quiebre >= UMBRAL_RIESGO_ALTO).length;

  const masConsumidos = [...prediccionProducto]
    .sort((a, b) => b.proyeccion_mes - a.proyeccion_mes)
    .slice(0, 3);

  // Cuatro cifras que responden "¿cómo estamos?" de un vistazo. El tono
  // (rojo/ámbar/verde) se decide acá para que el color diga si hay que
  // actuar, sin que la persona tenga que interpretar el número.
  const indicadores = [
    {
      titulo: 'Productos por agotarse',
      valor: productosPorAgotarse,
      ayuda: 'con alto riesgo de quedarse sin stock',
      tono: productosPorAgotarse > 0 ? 'malo' : 'bueno',
      Icono: FaExclamationTriangle,
    },
    {
      titulo: 'Gasto estimado del mes',
      valor: formatearCLP(presupuestoProyectado.mensual_clp),
      ayuda: 'para reponer lo que se va a consumir',
      tono: 'neutro',
      Icono: FaCoins,
    },
    {
      titulo: 'Consumos fuera de lo normal',
      valor: anomalias.length,
      ayuda: anomalias.length === 1 ? 'trabajador a revisar este mes' : 'trabajadores a revisar este mes',
      tono: anomalias.length > 0 ? 'alerta' : 'bueno',
      Icono: FaUserSecret,
    },
    {
      titulo: 'Dinero detenido en bodega',
      valor: formatearCLP(capitalInmovilizado.total_clp),
      ayuda: 'en productos con stock para más de 6 meses',
      tono: capitalInmovilizado.total_clp > 0 ? 'alerta' : 'bueno',
      Icono: FaBoxes,
    },
  ];

  return (
    <div className="gerencial-wrapper">
      <div className="gerencial-header">
        <div className="title-container">
          <h1><FaChartLine /> Panel Gerencial</h1>
          <p>Lo más importante de la bodega, explicado en simple. Se actualiza con cada entrega.</p>
        </div>

        <div className="header-actions">
          <button className="btn-export-dashboard" onClick={exportarDashboardExcel} disabled={loading}>
            <FaFileExcel /> Exportar Excel
          </button>
        </div>
      </div>

      {error && (
        <div className="prediction-box">
          <FaExclamationTriangle /> {error}
        </div>
      )}

      {/* ============ RESUMEN ============ */}
      <div className="gerencial-indicadores">
        {indicadores.map(({ titulo, valor, ayuda, tono, Icono }) => (
          <div key={titulo} className={`indicador indicador-${tono}`}>
            <div className="indicador-cabecera">
              <Icono className="indicador-icono" />
              <span>{titulo}</span>
            </div>
            <div className="indicador-valor">{loading ? '…' : valor}</div>
            <div className="indicador-ayuda">{ayuda}</div>
          </div>
        ))}
      </div>

      {/* ============ BUSCADOR ============ */}
      <div className="busqueda-card">
        <form className="busqueda-form" onSubmit={ejecutarBusqueda}>
          <FaSearch className="busqueda-icon" />

          <input
            type="text"
            className="busqueda-input"
            placeholder="Busca un producto: cascos, guantes, lentes..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />

          <button type="submit" className="busqueda-submit" disabled={busquedaLoading || !busqueda.trim()}>
            {busquedaLoading ? 'Buscando...' : 'Buscar'}
          </button>
        </form>

        {busquedaError && (
          <div className="fallback-msg fallback-msg-error">
            <FaExclamationTriangle /> {busquedaError}
          </div>
        )}

        {busquedaResultado && !busquedaError && (
          <div className="busqueda-resultado">
            {!busquedaResultado.confiable || (busquedaResultado.resultados || []).length === 0 ? (
              <div className="fallback-msg">
                <FaExclamationTriangle /> {busquedaResultado.motivo || 'Sin resultados para esa búsqueda.'}
              </div>
            ) : (
              busquedaResultado.resultados.map((r) => (
                <div key={r.inventario_id} className="busqueda-resultado-item">
                  <div className="busqueda-resultado-nombre">{r.producto_nombre}</div>
                  <p className="busqueda-resultado-texto">
                    {r.bodega_nombre}: quedan <strong>{r.stock_actual}</strong> unidades
                    {r.necesita_reposicion ? ' (bajo el mínimo)' : ''}. Se entregan unas{' '}
                    <strong>{r.consumo_mensual_estimado}</strong> al mes.
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* ============ ¿QUÉ HAY QUE COMPRAR? ============ */}
      <section className="seccion-gerencial">
        <div className="seccion-cabecera">
          <h2><FaShoppingCart /> ¿Qué hay que comprar?</h2>
          <p>Productos que conviene pedir ahora para no quedarse sin stock en faena.</p>
        </div>

        <div className="ml-table-wrapper">
          <table className="ml-table">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Bodega</th>
                <th>Pedir antes del</th>
                <th>Cantidad</th>
                <th>Urgencia</th>
              </tr>
            </thead>
            <tbody>
              {recomendaciones.length === 0 ? (
                <tr><td colSpan="5" className="ml-empty">Todo en orden: no hay que comprar nada por ahora.</td></tr>
              ) : (
                recomendaciones.slice(0, 8).map((r) => {
                  const urgencia = textoUrgencia(r.probabilidad_quiebre);
                  return (
                    <tr key={r.inventario_id}>
                      <td className="fw-bold" data-label="Producto">{r.producto_nombre}</td>
                      <td data-label="Bodega">{r.bodega_nombre}</td>
                      <td data-label="Pedir antes del">{formatearFecha(r.fecha_sugerida_pedido)}</td>
                      <td data-label="Cantidad">{r.cantidad_sugerida} un.</td>
                      <td data-label="Urgencia"><span className={`badge-riesgo ${urgencia.clase}`}>{urgencia.texto}</span></td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <p className="nota-calculo">
          Cómo se calcula: Regresión Logística con el stock, el consumo diario y el tiempo de entrega del proveedor.
        </p>
      </section>

      {/* ============ ¿CUÁNTO SE VA A CONSUMIR? ============ */}
      <section className="seccion-gerencial">
        <div className="seccion-cabecera">
          <h2><FaChartLine /> ¿Cuánto se va a consumir?</h2>
          <p>
            La próxima semana se espera entregar unas <strong>{prediccionSemanal.proyeccion_proxima_semana}</strong> unidades
            de EPP{!prediccionSemanal.confiable && ' (estimación preliminar: todavía hay poco historial)'}.
          </p>
        </div>

        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title">Unidades entregadas por semana</div>
            <div className="chart-subtitle">El punto celeste es lo estimado</div>
          </div>
          <div className="chart-container">
            <Line data={chartDataHistorico} options={chartOptionsConsumo} />
          </div>
        </div>

        {masConsumidos.length > 0 && (
          <p className="seccion-dato">
            Lo que más se consume:{' '}
            {masConsumidos.map((p, i) => (
              <span key={p.inventario_id}>
                {i > 0 && ' · '}
                <strong>{p.producto_nombre}</strong> ({p.proyeccion_mes} al mes)
              </span>
            ))}
            .
          </p>
        )}

        <p className="nota-calculo">
          Cómo se calcula: Regresión Lineal y Random Forest sobre las entregas de las últimas semanas.
        </p>
      </section>

      {/* ============ ¿HAY CONSUMOS FUERA DE LO NORMAL? ============ */}
      <section className="seccion-gerencial">
        <div className="seccion-cabecera">
          <h2><FaUserSecret /> ¿Hay consumos fuera de lo normal?</h2>
          <p>
            Trabajadores que este mes retiraron bastante más que otros con su mismo cargo. Es una señal
            para revisar, no una acusación.
          </p>
        </div>

        <div className="ml-list">
          {anomalias.length === 0 ? (
            <div className="ml-empty">Todo en orden: nadie se sale del consumo habitual este mes.</div>
          ) : (
            anomalias.map((a) => (
              <div key={`${a.trabajador_id}-${a.inventario_id}`} className="ml-item ml-item-danger">
                <FaUserSecret className="ml-item-icon" />
                <div className="ml-item-grow">
                  <div className="ml-item-title">{a.trabajador_nombre}</div>
                  <div className="ml-item-subtitle">{a.mensaje}</div>
                </div>
                <div className="ml-item-badge">
                  {a.impacto_financiero_clp > 0 ? formatearCLP(a.impacto_financiero_clp) : `${Math.round(a.cantidad_mes)} un.`}
                </div>
              </div>
            ))
          )}
        </div>

        <p className="nota-calculo">
          Cómo se calcula: K-Means agrupa a los trabajadores por su patrón de consumo.
        </p>
      </section>

      {/* ============ ¿DÓNDE ESTÁ EL DINERO? ============ */}
      <section className="seccion-gerencial">
        <div className="seccion-cabecera">
          <h2><FaCoins /> ¿Dónde está el dinero?</h2>
          <p>Los productos que concentran más valor y los que tienen más stock del necesario.</p>
        </div>

        {!abcConfiable && abcMotivo && (
          <div className="fallback-msg">
            <FaExclamationTriangle /> {abcMotivo}
          </div>
        )}

        <div className="valor-clases">
          {[
            { clase: 'A', nombre: 'Alto valor', detalle: 'control estricto' },
            { clase: 'B', nombre: 'Valor medio', detalle: 'control normal' },
            { clase: 'C', nombre: 'Consumo masivo', detalle: 'despacho ágil' },
          ].map(({ clase, nombre, detalle }) => (
            <div key={clase} className={`valor-clase valor-clase-${clase.toLowerCase()}`}>
              <div className="valor-clase-nombre">{nombre}</div>
              <div className="valor-clase-monto">{formatearCLP(resumenAbc[clase]?.valor_stock_clp)}</div>
              <div className="valor-clase-detalle">
                {resumenAbc[clase]?.cantidad || 0} producto(s) · {detalle}
              </div>
            </div>
          ))}
        </div>

        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title"><FaBoxes /> Exceso de stock</div>
            <div className="chart-subtitle">Se podría mover a otra faena o pausar su compra</div>
          </div>

          <div className="ml-table-wrapper">
            <table className="ml-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Alcanza para</th>
                  <th>Dinero detenido</th>
                </tr>
              </thead>
              <tbody>
                {capitalInmovilizado.items.length === 0 ? (
                  <tr><td colSpan="3" className="ml-empty">Sin exceso de stock.</td></tr>
                ) : (
                  capitalInmovilizado.items.slice(0, 6).map((c) => (
                    <tr key={c.inventario_id}>
                      <td className="fw-bold" data-label="Producto">{c.producto_nombre}</td>
                      <td data-label="Alcanza para">
                        {c.dias_cobertura_estimados ? `${Math.round(c.dias_cobertura_estimados / 30)} meses` : 'Sin consumo reciente'}
                      </td>
                      <td data-label="Dinero detenido">{formatearCLP(c.capital_inmovilizado_clp)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <p className="nota-calculo">
          Cómo se calcula: K-Means clasifica el catálogo por precio y rotación (clasificación ABC).
        </p>
      </section>
    </div>
  );
};

export default DashboardGerencial;
