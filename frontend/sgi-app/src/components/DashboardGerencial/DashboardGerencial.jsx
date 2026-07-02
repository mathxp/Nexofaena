import { useState, useEffect } from 'react';
import {
  FaUserFriends,
  FaBoxOpen,
  FaChartLine,
  FaCircle,
  FaChartBar,
  FaExclamationTriangle,
  FaBrain,
  FaWarehouse,
  FaFileExcel,
} from 'react-icons/fa';

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

import { Bar, Line } from 'react-chartjs-2';
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
  Title,
  Tooltip,
  Legend,
  Filler
);

const emptyChart = {
  labels: ['Sin datos'],
  data: [0],
};

const normalizarChart = (chart) => {
  if (!chart || !Array.isArray(chart.labels) || !Array.isArray(chart.data)) {
    return emptyChart;
  }

  if (chart.labels.length === 0 || chart.data.length === 0) {
    return emptyChart;
  }

  return {
    labels: chart.labels.map((label) => String(label || 'Sin dato')),
    data: chart.data.map((value) => {
      const numero = Number(value);
      return Number.isFinite(numero) ? numero : 0;
    }),
  };
};

const DashboardGerencial = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [kpis, setKpis] = useState({
    trabajadores_activos: 0,
    productos_inventariados: 0,
    stock_total: 0,
    salidas_mes: 0,
    alertas_activas: 0,
    productos_criticos: 0,
    productos_bajo_minimo: 0,
    productos_sobre_stock: 0,
  });

  const [entregasMensuales, setEntregasMensuales] = useState(emptyChart);
  const [topProductos, setTopProductos] = useState(emptyChart);
  const [consumoBodega, setConsumoBodega] = useState(emptyChart);
  const [alertas, setAlertas] = useState(emptyChart);
  const [stockEstado, setStockEstado] = useState(emptyChart);
  const [prediccionSiguienteMes, setPrediccionSiguienteMes] = useState(0);

  useEffect(() => {
    cargarDashboard();
  }, []);

  const cargarDashboard = async () => {
    try {
      setLoading(true);
      setError('');

      const response = await api.get('/dashboard/resumen/');
      const data = response.data || {};

      const entregas = normalizarChart(data.entregas_mensuales);
      const productos = normalizarChart(data.top_productos);
      const bodegas = normalizarChart(data.consumo_bodega);
      const alertasData = normalizarChart(data.alertas);
      const stock = normalizarChart(data.stock_estado);

      setKpis({
        trabajadores_activos: Number(data.kpis?.trabajadores_activos || 0),
        productos_inventariados: Number(data.kpis?.productos_inventariados || 0),
        stock_total: Number(data.kpis?.stock_total || 0),
        salidas_mes: Number(data.kpis?.salidas_mes || 0),
        alertas_activas: Number(data.kpis?.alertas_activas || 0),
        productos_criticos: Number(data.kpis?.productos_criticos || 0),
        productos_bajo_minimo: Number(data.kpis?.productos_bajo_minimo || 0),
        productos_sobre_stock: Number(data.kpis?.productos_sobre_stock || 0),
      });

      setEntregasMensuales(entregas);
      setTopProductos(productos);
      setConsumoBodega(bodegas);
      setAlertas(alertasData);
      setStockEstado(stock);
      calcularProyeccion(entregas.data);
    } catch (err) {
      console.error(err);
      setError('No se pudo cargar el Dashboard Gerencial.');
    } finally {
      setLoading(false);
    }
  };

  const calcularProyeccion = (dataY) => {
    const valores = Array.isArray(dataY) ? dataY.map((v) => Number(v || 0)) : [];

    if (valores.length === 0) {
      setPrediccionSiguienteMes(0);
      return;
    }

    const n = valores.length;
    let sumX = 0;
    let sumY = 0;
    let sumXY = 0;
    let sumXX = 0;

    valores.forEach((y, x) => {
      sumX += x;
      sumY += y;
      sumXY += x * y;
      sumXX += x * x;
    });

    const denominator = n * sumXX - sumX * sumX;

    if (denominator === 0) {
      setPrediccionSiguienteMes(0);
      return;
    }

    const m = (n * sumXY - sumX * sumY) / denominator;
    const b = (sumY - m * sumX) / n;

    setPrediccionSiguienteMes(Math.max(0, Math.round(m * n + b)));
  };

  const exportarDashboardExcel = async () => {
    const workbook = new ExcelJS.Workbook();
    workbook.creator = 'NexoFaena SGI';
    workbook.created = new Date();

    const resumen = workbook.addWorksheet('Resumen Gerencial', {
      views: [{ showGridLines: false }],
    });

    const graficos = workbook.addWorksheet('Datos de Gráficos', {
      views: [{ showGridLines: false }],
    });

    resumen.mergeCells('A1:D1');
    resumen.getCell('A1').value = 'NEXOFAENA SGI - DASHBOARD GERENCIAL';
    resumen.getCell('A1').font = { bold: true, size: 16, color: { argb: 'FFFFFFFF' } };
    resumen.getCell('A1').fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF001529' },
    };
    resumen.getCell('A1').alignment = { horizontal: 'center', vertical: 'middle' };
    resumen.getRow(1).height = 30;

    resumen.addRow([]);
    resumen.addRow(['Generado', new Date().toLocaleString()]);
    resumen.addRow(['Trabajadores activos', kpis.trabajadores_activos]);
    resumen.addRow(['Productos inventariados', kpis.productos_inventariados]);
    resumen.addRow(['Stock total', kpis.stock_total]);
    resumen.addRow(['Salidas del mes', kpis.salidas_mes]);
    resumen.addRow(['Productos críticos', kpis.productos_criticos]);
    resumen.addRow(['Productos bajo mínimo', kpis.productos_bajo_minimo]);
    resumen.addRow(['Productos sobre stock', kpis.productos_sobre_stock]);
    resumen.addRow(['Alertas activas', kpis.alertas_activas]);
    resumen.addRow(['Proyección próximo mes', prediccionSiguienteMes]);

    resumen.columns = [
      { width: 34 },
      { width: 24 },
      { width: 22 },
      { width: 22 },
    ];

    resumen.eachRow((row, rowNumber) => {
      row.eachCell((cell) => {
        cell.border = {
          bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        };

        if (rowNumber >= 3) {
          cell.alignment = { vertical: 'middle' };
        }
      });
    });

    const agregarSeccionGrafico = (titulo, chart) => {
      graficos.addRow([]);

      const titleRow = graficos.addRow([titulo]);
      titleRow.getCell(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
      titleRow.getCell(1).fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FFEA580C' },
      };

      const header = graficos.addRow(['Etiqueta', 'Valor']);
      header.eachCell((cell) => {
        cell.font = { bold: true };
        cell.fill = {
          type: 'pattern',
          pattern: 'solid',
          fgColor: { argb: 'FFF3F4F6' },
        };
      });

      chart.labels.forEach((label, index) => {
        graficos.addRow([label, chart.data[index] || 0]);
      });
    };

    graficos.columns = [
      { width: 42 },
      { width: 18 },
    ];

    agregarSeccionGrafico('Entregas por mes', entregasMensuales);
    agregarSeccionGrafico('Top productos consumidos', topProductos);
    agregarSeccionGrafico('Consumo por bodega', consumoBodega);
    agregarSeccionGrafico('Estado del stock', stockEstado);
    agregarSeccionGrafico('Alertas generadas', alertas);

    graficos.eachRow((row) => {
      row.eachCell((cell) => {
        cell.border = {
          bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        };
        cell.alignment = { vertical: 'middle' };
      });
    });

    const buffer = await workbook.xlsx.writeBuffer();

    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    saveAs(blob, `NexoFaena_Dashboard_Gerencial_${Date.now()}.xlsx`);
  };

  ChartJS.defaults.color = '#94a3b8';
  ChartJS.defaults.font.family = "'Inter', sans-serif";

  const chartOptionsBase = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(255,255,255,0.08)' },
      },
      x: {
        grid: { display: false },
      },
    },
  };

  const chartOptionsHorizontal = {
    ...chartOptionsBase,
    indexAxis: 'y',
  };

  const chartDataEntregas = {
    labels: entregasMensuales.labels,
    datasets: [
      {
        label: 'Entregas',
        data: entregasMensuales.data,
        backgroundColor: '#ea580c',
        borderRadius: 4,
        barThickness: 30,
      },
    ],
  };

  const chartDataTopProductos = {
    labels: topProductos.labels,
    datasets: [
      {
        label: 'Unidades',
        data: topProductos.data,
        backgroundColor: '#fb923c',
        borderRadius: 4,
      },
    ],
  };

  const chartDataConsumoBodega = {
    labels: consumoBodega.labels,
    datasets: [
      {
        label: 'Unidades',
        data: consumoBodega.data,
        backgroundColor: '#10b981',
        borderRadius: 4,
      },
    ],
  };

  const chartDataAlertas = {
    labels: alertas.labels,
    datasets: [
      {
        label: 'Alertas',
        data: alertas.data,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.2)',
        fill: true,
        tension: 0.4,
      },
    ],
  };

  const chartDataStockEstado = {
    labels: stockEstado.labels,
    datasets: [
      {
        label: 'Productos',
        data: stockEstado.data,
        backgroundColor: '#60a5fa',
        borderRadius: 4,
      },
    ],
  };

  return (
    <div className="gerencial-wrapper">
      <div className="gerencial-header">
        <div className="title-container">
          <h1>DASHBOARD GERENCIAL - BODEGA</h1>
          <p>Jefaturas y Administración</p>
        </div>

        <div className="header-actions">
          <div className="status-badge">
            <FaCircle /> {loading ? 'CARGANDO' : 'CONECTADO'}
          </div>

          <button
            className="btn-export-dashboard"
            onClick={exportarDashboardExcel}
            disabled={loading}
          >
            <FaFileExcel /> Exportar Excel
          </button>
        </div>
      </div>

      {error && (
        <div className="prediction-box">
          <FaExclamationTriangle /> {error}
        </div>
      )}

      <div className="kpi-gerencial-grid">
        <div className="kpi-gerencial-card kpi-border-blue">
          <div className="kpi-header">
            <FaUserFriends /> Trabajadores activos
          </div>
          <h2 className="kpi-value">{kpis.trabajadores_activos}</h2>
          <div className="kpi-trend">Personal operativo</div>
        </div>

        <div className="kpi-gerencial-card kpi-border-orange">
          <div className="kpi-header">
            <FaBoxOpen /> Productos inventariados
          </div>
          <h2 className="kpi-value">{kpis.productos_inventariados}</h2>
          <div className="kpi-trend">Stock controlado</div>
        </div>

        <div className="kpi-gerencial-card kpi-border-green">
          <div className="kpi-header">
            <FaChartLine /> Salidas del mes
          </div>
          <h2 className="kpi-value">{kpis.salidas_mes}</h2>
          <div className="kpi-trend">Movimientos tipo salida</div>
        </div>

        <div className="kpi-gerencial-card kpi-border-orange">
          <div className="kpi-header">
            <FaWarehouse /> Stock total
          </div>
          <h2 className="kpi-value">{kpis.stock_total}</h2>
          <div className="kpi-trend">Unidades disponibles</div>
        </div>

        <div className="kpi-gerencial-card kpi-border-blue">
          <div className="kpi-header">
            <FaExclamationTriangle /> Productos críticos
          </div>
          <h2 className="kpi-value">{kpis.productos_criticos}</h2>
          <div className="kpi-trend">Bajo stock mínimo</div>
        </div>

        <div className="kpi-gerencial-card kpi-border-green">
          <div className="kpi-header">
            <FaExclamationTriangle /> Alertas activas
          </div>
          <h2 className="kpi-value">{kpis.alertas_activas}</h2>
          <div className="kpi-trend">No leídas</div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title">
              <FaChartBar /> Entregas por Mes
            </div>
            <div className="chart-subtitle">Historial</div>
          </div>

          <div className="chart-container">
            <Bar data={chartDataEntregas} options={chartOptionsBase} />
          </div>

          <div className="prediction-box">
            <FaBrain /> Proyección: <strong>{prediccionSiguienteMes}</strong> entregas estimadas.
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title">
              <FaBoxOpen /> Top productos consumidos
            </div>
            <div className="chart-subtitle">Top 5</div>
          </div>

          <div className="chart-container">
            <Bar data={chartDataTopProductos} options={chartOptionsHorizontal} />
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title">
              <FaChartLine /> Consumo por bodega
            </div>
            <div className="chart-subtitle">Salidas acumuladas</div>
          </div>

          <div className="chart-container">
            <Bar data={chartDataConsumoBodega} options={chartOptionsHorizontal} />
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title">
              <FaExclamationTriangle /> Estado del stock
            </div>
            <div className="chart-subtitle">Crítico, bajo, óptimo y sobre stock</div>
          </div>

          <div className="chart-container">
            <Bar data={chartDataStockEstado} options={chartOptionsBase} />
          </div>
        </div>

        <div className="chart-card full-width">
          <div className="chart-header">
            <div className="chart-title">
              <FaExclamationTriangle /> Alertas generadas
            </div>
            <div className="chart-subtitle">Historial</div>
          </div>

          <div className="chart-container">
            <Line data={chartDataAlertas} options={chartOptionsBase} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardGerencial;