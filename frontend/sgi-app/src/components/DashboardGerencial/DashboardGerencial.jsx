import { useState, useEffect } from 'react';
import {
  FaRobot,
  FaCircle,
  FaExclamationTriangle,
  FaBrain,
  FaFileExcel,
  FaChartLine,
  FaShoppingCart,
  FaShieldAlt,
  FaUserSecret,
  FaProjectDiagram,
  FaShippingFast,
  FaSearch,
  FaLink,
  FaHandshake,
  FaArrowRight,
  FaUserShield,
  FaChartPie,
  FaFlag,
} from 'react-icons/fa';

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

import { Bar, Line, Doughnut } from 'react-chartjs-2';
import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import './DashboardGerencial.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const UMBRAL_RIESGO_ALTO = 70;
const UMBRAL_RIESGO_MEDIO = 40;

const badgeRiesgo = (probabilidad) => {
  if (probabilidad >= UMBRAL_RIESGO_ALTO) return 'riesgo-alto';
  if (probabilidad >= UMBRAL_RIESGO_MEDIO) return 'riesgo-medio';
  return 'riesgo-bajo';
};

const colorRiesgo = (probabilidad) => {
  if (probabilidad >= UMBRAL_RIESGO_ALTO) return '#ef4444';
  if (probabilidad >= UMBRAL_RIESGO_MEDIO) return '#f59e0b';
  return '#60a5fa';
};

const claseNivelRiesgo = (nivel) => {
  if (nivel === 'Alto') return 'riesgo-alto';
  if (nivel === 'Medio') return 'riesgo-medio';
  return 'riesgo-bajo';
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
  const [quiebreStock, setQuiebreStock] = useState([]);
  const [recomendaciones, setRecomendaciones] = useState([]);
  const [anomalias, setAnomalias] = useState([]);

  const [reglasAsociacion, setReglasAsociacion] = useState([]);
  const [reglasConfiable, setReglasConfiable] = useState(false);
  const [reglasMotivo, setReglasMotivo] = useState('');

  const [perfilRiesgo, setPerfilRiesgo] = useState([]);
  const [riesgoConfiable, setRiesgoConfiable] = useState(false);
  const [riesgoMotivo, setRiesgoMotivo] = useState('');

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
        setQuiebreStock(Array.isArray(data.quiebre_stock) ? data.quiebre_stock : []);
        setRecomendaciones(Array.isArray(data.recomendaciones_reposicion) ? data.recomendaciones_reposicion : []);
        setAnomalias(Array.isArray(data.anomalias_consumo) ? data.anomalias_consumo : []);
      } else {
        console.error(resumenRes.reason);
        setError('No se pudo cargar el Modelo Predictivo de Inteligencia Artificial.');
      }

      if (mlAvanzadoRes.status === 'fulfilled') {
        const data = mlAvanzadoRes.value.data || {};
        const reglas = data.recomendaciones_epp || {};
        const riesgo = data.perfil_riesgo || {};

        setReglasAsociacion(Array.isArray(reglas.reglas) ? reglas.reglas : []);
        setReglasConfiable(Boolean(reglas.confiable));
        setReglasMotivo(reglas.motivo || '');

        setPerfilRiesgo(Array.isArray(riesgo.trabajadores) ? riesgo.trabajadores : []);
        setRiesgoConfiable(Boolean(riesgo.confiable));
        setRiesgoMotivo(riesgo.motivo || '');
      } else {
        console.error(mlAvanzadoRes.reason);
        setReglasAsociacion([]);
        setReglasConfiable(false);
        setReglasMotivo('No se pudo cargar el módulo de asociación de EPP.');
        setPerfilRiesgo([]);
        setRiesgoConfiable(false);
        setRiesgoMotivo('No se pudo cargar el perfil de riesgo operativo.');
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

    const estiloTitulo = (cell, texto, color = 'FF001529') => {
      cell.value = texto;
      cell.font = { bold: true, size: 14, color: { argb: 'FFFFFFFF' } };
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: color } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
    };

    const estiloHeader = (row) => {
      row.eachCell((cell) => {
        cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEA580C' } };
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
      });
    };

    const resumen = workbook.addWorksheet('Resumen IA');
    resumen.mergeCells('A1:D1');
    estiloTitulo(resumen.getCell('A1'), 'NEXOFAENA SGI - MODELO PREDICTIVO DE INTELIGENCIA ARTIFICIAL');
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
    headerReco.getCell(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF001529' } };
    const headerReco2 = prevencion.addRow(['Producto', 'Bodega', 'Pedir antes de', 'Cantidad sugerida', 'Riesgo']);
    estiloHeader(headerReco2);
    recomendaciones.forEach((r) => {
      prevencion.addRow([
        r.producto_nombre,
        r.bodega_nombre,
        new Date(r.fecha_sugerida_pedido).toLocaleDateString(),
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

  ChartJS.defaults.color = '#94a3b8';
  ChartJS.defaults.font.family = "'Inter', sans-serif";

  const chartOptionsBase = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.08)' } },
      x: { grid: { display: false } },
    },
  };

  const chartDataHistorico = {
    labels: [...prediccionSemanal.historico.labels, 'Próxima semana'],
    datasets: [
      {
        label: 'Unidades consumidas',
        data: [...prediccionSemanal.historico.data, null],
        borderColor: '#ea580c',
        backgroundColor: 'rgba(234, 88, 12, 0.15)',
        fill: true,
        tension: 0.35,
      },
      {
        label: 'Proyección (Regresión Lineal)',
        data: [
          ...prediccionSemanal.historico.data.map(() => null),
          prediccionSemanal.proyeccion_proxima_semana,
        ],
        borderColor: '#60a5fa',
        backgroundColor: '#60a5fa',
        pointRadius: 6,
        showLine: false,
      },
    ],
  };

  const top6Riesgo = quiebreStock.slice(0, 6);

  const chartDataRiesgo = {
    labels: top6Riesgo.map((q) => q.producto_nombre),
    datasets: [
      {
        label: 'Probabilidad de quiebre (%)',
        data: top6Riesgo.map((q) => q.probabilidad_quiebre),
        backgroundColor: top6Riesgo.map((q) => colorRiesgo(q.probabilidad_quiebre)),
        borderRadius: 4,
      },
    ],
  };

  const conteoPorNivelRiesgo = perfilRiesgo.reduce((acc, p) => {
    acc[p.nivel_riesgo] = (acc[p.nivel_riesgo] || 0) + 1;
    return acc;
  }, {});

  const chartDataNivelRiesgo = {
    labels: ['Bajo', 'Medio', 'Alto'],
    datasets: [
      {
        data: ['Bajo', 'Medio', 'Alto'].map((nivel) => conteoPorNivelRiesgo[nivel] || 0),
        backgroundColor: ['#60a5fa', '#fbbf24', '#ef4444'],
        borderColor: '#001e38',
        borderWidth: 2,
      },
    ],
  };

  return (
    <div className="gerencial-wrapper">
      <div className="gerencial-header">
        <div className="title-container">
          <h1><FaRobot /> Modelo Predictivo de Inteligencia Artificial</h1>
          <p>Motor de IA de NexoFaena SGI — Planificación, prevención y auditoría de bodega</p>
        </div>

        <div className="header-actions">
          <div className="status-badge">
            <FaCircle /> {loading ? 'ENTRENANDO MODELOS' : 'MODELOS ACTIVOS'}
          </div>

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

      {/* ============ BUSCADOR SEMÁNTICO (NLP) ============ */}
      <div className="busqueda-card">
        <form className="busqueda-form" onSubmit={ejecutarBusqueda}>
          <FaSearch className="busqueda-icon" />

          <input
            type="text"
            className="busqueda-input"
            placeholder="Ej: Resume el consumo de cascos del mes..."
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
              <>
                <div className="busqueda-resultado-header">
                  <FaBrain /> Resultados para “{busquedaResultado.consulta}”
                  <span className="tag-algoritmo">{busquedaResultado.algoritmo}</span>
                </div>

                {busquedaResultado.resultados.map((r) => (
                  <div key={r.inventario_id} className="busqueda-resultado-item">
                    <div className="busqueda-resultado-nombre">
                      {r.producto_nombre}
                      <span className="tag-algoritmo">{r.similitud}% similitud</span>
                    </div>
                    <p className="busqueda-resultado-texto">
                      {r.bodega_nombre}: stock actual de {r.stock_actual} unidades
                      {r.necesita_reposicion ? ', por debajo del mínimo' : ''}, consumo diario promedio de{' '}
                      {r.consumo_diario_promedio} uds (~{r.consumo_mensual_estimado} uds/mes).
                    </p>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* ============ MÓDULO 1: REGRESIÓN LINEAL / RANDOM FOREST ============ */}
      <div className="modulo-ia">
        <div className="modulo-header">
          <div className="modulo-icon modulo-icon-blue"><FaChartLine /></div>
          <div>
            <div className="modulo-badge">Regresión Lineal · Random Forest</div>
            <h2 className="modulo-title">Planificación y Compras</h2>
            <p className="modulo-desc">
              Analiza las entregas históricas y proyecta la demanda futura de cada producto para
              recomendar cuánto comprar, sin adivinar.
            </p>
          </div>
        </div>

        <div className="modulo-impacto">
          <FaBrain /> Impacto: en vez de que el bodeguero adivine, el sistema indica exactamente cuánto
          material se espera consumir y sugiere cantidades de compra — optimizando presupuesto y evitando
          compras a ciegas.
        </div>

        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-header">
              <div className="chart-title"><FaChartLine /> Consumo semanal e histórico</div>
              <div className="chart-subtitle">Últimas {prediccionSemanal.historico.labels.length} semanas</div>
            </div>

            <div className="chart-container">
              <Line data={chartDataHistorico} options={chartOptionsBase} />
            </div>

            <div className="prediction-box">
              <FaBrain /> Proyección próxima semana: <strong>{prediccionSemanal.proyeccion_proxima_semana}</strong> unidades
              {!prediccionSemanal.confiable && ' (histórico aún limitado)'}
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-header">
              <div className="chart-title"><FaShoppingCart /> Consumo esperado por producto</div>
              <div className="chart-subtitle">Próxima semana / mes</div>
            </div>

            <div className="ml-table-wrapper">
              <table className="ml-table">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Semana</th>
                    <th>Mes</th>
                    <th>Modelo</th>
                  </tr>
                </thead>
                <tbody>
                  {prediccionProducto.length === 0 ? (
                    <tr><td colSpan="4" className="ml-empty">Sin historial suficiente todavía.</td></tr>
                  ) : (
                    prediccionProducto.slice(0, 6).map((p) => (
                      <tr key={p.inventario_id}>
                        <td>{p.producto_nombre}</td>
                        <td>{p.proyeccion_semana}</td>
                        <td>{p.proyeccion_mes}</td>
                        <td><span className="tag-algoritmo">{p.algoritmo}</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* ============ MÓDULO 2: REGRESIÓN LOGÍSTICA ============ */}
      <div className="modulo-ia">
        <div className="modulo-header">
          <div className="modulo-icon modulo-icon-red"><FaShieldAlt /></div>
          <div>
            <div className="modulo-badge">Regresión Logística</div>
            <h2 className="modulo-title">Prevención Operativa</h2>
            <p className="modulo-desc">
              Cruza el inventario actual, la velocidad de consumo y el tiempo de reposición del proveedor
              para calcular la probabilidad real de quedarse sin stock.
            </p>
          </div>
        </div>

        <div className="modulo-impacto modulo-impacto-red">
          <FaExclamationTriangle /> Impacto: alertas visuales preventivas con el porcentaje exacto de
          riesgo de quiebre (ej. 85%), evitando que la faena se paralice por falta de materiales críticos.
        </div>

        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-header">
              <div className="chart-title"><FaShieldAlt /> Riesgo de quiebre por producto</div>
              <div className="chart-subtitle">Top 6 más críticos</div>
            </div>

            <div className="chart-container">
              {quiebreStock.length === 0 ? (
                <div className="ml-empty">Sin riesgo relevante detectado.</div>
              ) : (
                <Bar data={chartDataRiesgo} options={{ ...chartOptionsBase, indexAxis: 'y', scales: { x: { max: 100, grid: { color: 'rgba(255,255,255,0.08)' } }, y: { grid: { display: false } } } }} />
              )}
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-header">
              <div className="chart-title"><FaShippingFast /> Recomendación de reposición</div>
              <div className="chart-subtitle">Cuándo y cuánto pedir</div>
            </div>

            <div className="ml-table-wrapper">
              <table className="ml-table">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Pedir antes de</th>
                    <th>Cantidad</th>
                    <th>Riesgo</th>
                  </tr>
                </thead>
                <tbody>
                  {recomendaciones.length === 0 ? (
                    <tr><td colSpan="4" className="ml-empty">No hay reposiciones urgentes por ahora.</td></tr>
                  ) : (
                    recomendaciones.slice(0, 6).map((r) => (
                      <tr key={r.inventario_id}>
                        <td>{r.producto_nombre}</td>
                        <td>{new Date(r.fecha_sugerida_pedido).toLocaleDateString()}</td>
                        <td>{r.cantidad_sugerida} un.</td>
                        <td><span className={`badge-riesgo ${badgeRiesgo(r.probabilidad_quiebre)}`}>{r.probabilidad_quiebre}%</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* ============ MÓDULO 3: K-MEANS ============ */}
      <div className="modulo-ia">
        <div className="modulo-header">
          <div className="modulo-icon modulo-icon-orange"><FaProjectDiagram /></div>
          <div>
            <div className="modulo-badge">K-Means (Clustering)</div>
            <h2 className="modulo-title">Auditoría y "Robo Hormiga"</h2>
            <p className="modulo-desc">
              Agrupa automáticamente a los trabajadores según su patrón de consumo normal. Quien se sale
              del clúster por un consumo inusual queda aislado matemáticamente.
            </p>
          </div>
        </div>

        <div className="modulo-impacto modulo-impacto-orange">
          <FaUserSecret /> Impacto: el sistema marca automáticamente una alerta de consumo anormal,
          frenando mermas, mal uso y robo hormiga sin revisar los registros uno por uno.
        </div>

        <div className="ml-list">
          {anomalias.length === 0 ? (
            <div className="ml-empty">Sin anomalías de consumo detectadas este mes.</div>
          ) : (
            anomalias.map((a, idx) => (
              <div key={idx} className="ml-item ml-item-danger">
                <FaUserSecret className="ml-item-icon" />
                <div className="ml-item-grow">
                  <div className="ml-item-title">
                    {a.trabajador_nombre} <span className="tag-algoritmo">{a.algoritmo}</span>
                  </div>
                  <div className="ml-item-subtitle">{a.mensaje}</div>
                </div>
                <div className="ml-item-badge">{Math.round(a.cantidad_mes)} un.</div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ============ MÓDULO 4: REGLAS DE ASOCIACIÓN ============ */}
      <div className="modulo-ia">
        <div className="modulo-header">
          <div className="modulo-icon modulo-icon-purple"><FaLink /></div>
          <div>
            <div className="modulo-badge">Reglas de Asociación</div>
            <h2 className="modulo-title">Recomendador de EPP (Cross-Selling)</h2>
            <p className="modulo-desc">
              Analiza qué productos se entregan juntos con más frecuencia de lo que explicaría el
              azar, para que el pañolero ofrezca proactivamente el complemento correcto.
            </p>
          </div>
        </div>

        <div className="modulo-impacto modulo-impacto-purple">
          <FaHandshake /> Impacto: reduce los viajes de vuelta al pañol por un EPP olvidado y
          refuerza el uso completo de equipos que van en conjunto (ej. arnés + cabo de vida).
        </div>

        {!reglasConfiable ? (
          <div className="fallback-msg">
            <FaExclamationTriangle /> {reglasMotivo || 'Datos insuficientes para entrenamiento. Mostrando cálculo base.'}
          </div>
        ) : reglasAsociacion.length === 0 ? (
          <div className="ml-empty">Sin asociaciones relevantes detectadas todavía.</div>
        ) : (
          <div className="ml-list">
            {reglasAsociacion.map((r, idx) => (
              <div key={idx} className="ml-item ml-item-purple">
                <FaLink className="ml-item-icon ml-item-icon-purple" />
                <div className="ml-item-grow">
                  <div className="ml-item-title">
                    {r.producto_origen} <FaArrowRight className="ml-item-arrow" /> {r.producto_sugerido}
                    <span className="tag-algoritmo">lift {r.lift}</span>
                  </div>
                  <div className="ml-item-subtitle">{r.mensaje}</div>
                </div>
                <div className="ml-item-badge ml-item-badge-purple">{r.confianza}%</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ============ MÓDULO 5: RANDOM FOREST CLASSIFIER ============ */}
      <div className="modulo-ia">
        <div className="modulo-header">
          <div className="modulo-icon modulo-icon-cyan"><FaUserShield /></div>
          <div>
            <div className="modulo-badge">Random Forest Classifier</div>
            <h2 className="modulo-title">Perfil de Riesgo Operativo</h2>
            <p className="modulo-desc">
              Clasifica a cada trabajador según su tasa de reposición de activos críticos, para
              levantar una bandera roja antes de entregarle otro equipo costoso.
            </p>
          </div>
        </div>

        <div className="modulo-impacto modulo-impacto-cyan">
          <FaExclamationTriangle /> Impacto: anticipa pérdidas repetidas de herramientas de alto
          valor en vez de descubrirlas recién en el siguiente conteo cíclico.
        </div>

        {!riesgoConfiable && (
          <div className="fallback-msg">
            <FaExclamationTriangle /> {riesgoMotivo || 'Datos insuficientes para entrenamiento. Mostrando cálculo base.'}
          </div>
        )}

        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-header">
              <div className="chart-title"><FaChartPie /> Distribución de riesgo</div>
              <div className="chart-subtitle">{perfilRiesgo.length} trabajador(es) con activos críticos</div>
            </div>

            <div className="chart-container">
              {perfilRiesgo.length === 0 ? (
                <div className="ml-empty">Sin trabajadores con entregas de activos críticos todavía.</div>
              ) : (
                <Doughnut
                  data={chartDataNivelRiesgo}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 14 } } },
                  }}
                />
              )}
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-header">
              <div className="chart-title"><FaUserShield /> Trabajadores en riesgo</div>
              <div className="chart-subtitle">Ordenado por tasa de reposición</div>
            </div>

            <div className="ml-table-wrapper">
              <table className="ml-table">
                <thead>
                  <tr>
                    <th>Trabajador</th>
                    <th>Reposición</th>
                    <th>Nivel</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {perfilRiesgo.length === 0 ? (
                    <tr><td colSpan="4" className="ml-empty">Sin datos suficientes todavía.</td></tr>
                  ) : (
                    perfilRiesgo.slice(0, 6).map((p) => (
                      <tr key={p.trabajador_id}>
                        <td>
                          {p.trabajador_nombre}
                          <div className="ml-table-subtext">{p.cargo}</div>
                        </td>
                        <td>{p.tasa_reposicion}%</td>
                        <td><span className={`badge-riesgo ${claseNivelRiesgo(p.nivel_riesgo)}`}>{p.nivel_riesgo}</span></td>
                        <td>
                          {p.bandera_roja && (
                            <FaFlag className="bandera-roja" title="Evaluar antes de entregar otro activo crítico" />
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardGerencial;
