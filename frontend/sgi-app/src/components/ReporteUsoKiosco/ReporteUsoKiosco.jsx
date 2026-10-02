import { useState, useEffect, useCallback } from 'react';
import {
  FaDesktop,
  FaSearch,
  FaCalendarAlt,
  FaMapMarkerAlt,
  FaFileExcel,
  FaExclamationTriangle,
  FaUserTie,
  FaChartBar,
  FaPercentage,
  FaBoxes,
} from 'react-icons/fa';

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import './ReporteUsoKiosco.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const fechaISO = (date) => date.toISOString().slice(0, 10);

const filtrosPorDefecto = () => {
  const hoy = new Date();
  const hace30Dias = new Date();
  hace30Dias.setDate(hoy.getDate() - 30);

  return {
    fechaDesde: fechaISO(hace30Dias),
    fechaHasta: fechaISO(hoy),
    bodega: '',
  };
};

const reporteVacio = {
  periodo: { fecha_desde: '', fecha_hasta: '' },
  resumen_general: { total_entregas: 0, total_kiosco: 0, total_bodega: 0, porcentaje_kiosco: 0 },
  por_dia: [],
  por_turno: [],
  por_bodega: [],
};

const etiquetaTurno = (turno) => (turno === 'dia' ? 'Día' : turno === 'noche' ? 'Noche' : turno);

const ReporteUsoKiosco = () => {
  const [filtros, setFiltros] = useState(filtrosPorDefecto);
  const [bodegas, setBodegas] = useState([]);
  const [reporte, setReporte] = useState(reporteVacio);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const cargarReporte = useCallback(async (filtrosActuales) => {
    setCargando(true);
    setError('');

    const params = {
      fecha_desde: filtrosActuales.fechaDesde,
      fecha_hasta: filtrosActuales.fechaHasta,
    };
    if (filtrosActuales.bodega) params.bodega = filtrosActuales.bodega;

    try {
      const res = await api.get('/reportes/uso-kiosco/', { params });
      setReporte({ ...reporteVacio, ...res.data });
    } catch (err) {
      console.error(err);
      setError('No se pudo generar el reporte. Verifica tu conexión.');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    api.get('/bodegas/').then((res) => setBodegas(res.data)).catch(() => setBodegas([]));
    cargarReporte(filtros);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleBuscar = (e) => {
    e.preventDefault();
    cargarReporte(filtros);
  };

  const handleChange = (campo, valor) => {
    setFiltros((prev) => ({ ...prev, [campo]: valor }));
  };

  ChartJS.defaults.color = '#94a3b8';
  ChartJS.defaults.font.family = "'Inter', sans-serif";

  const chartDataPorDia = {
    labels: reporte.por_dia.map((f) => new Date(f.fecha).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' })),
    datasets: [
      {
        label: 'Kiosco (autoservicio)',
        data: reporte.por_dia.map((f) => f.kiosco),
        backgroundColor: '#22d3ee',
        borderRadius: 4,
      },
      {
        label: 'Bodeguero (manual)',
        data: reporte.por_dia.map((f) => f.bodega),
        backgroundColor: '#64748b',
        borderRadius: 4,
      },
    ],
  };

  const exportarExcel = async () => {
    if (reporte.por_dia.length === 0) {
      alert('No hay datos para exportar con estos filtros.');
      return;
    }

    const workbook = new ExcelJS.Workbook();
    workbook.creator = 'NexoFaena SGI';
    workbook.created = new Date();

    const estiloHeader = (row, color = 'FFEA580C') => {
      row.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      row.eachCell((cell) => {
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: color } };
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
      });
    };

    const porDia = workbook.addWorksheet('Uso por día');
    porDia.columns = [
      { header: 'Fecha', key: 'fecha', width: 16 },
      { header: 'Kiosco', key: 'kiosco', width: 14 },
      { header: 'Bodeguero', key: 'bodega', width: 14 },
      { header: 'Total', key: 'total', width: 14 },
    ];
    estiloHeader(porDia.getRow(1));
    reporte.por_dia.forEach((f) => {
      porDia.addRow({ fecha: f.fecha, kiosco: f.kiosco, bodega: f.bodega, total: f.total });
    });

    const porTurno = workbook.addWorksheet('Uso por turno');
    porTurno.columns = [
      { header: 'Turno', key: 'turno', width: 14 },
      { header: 'Kiosco', key: 'kiosco', width: 14 },
      { header: 'Bodeguero', key: 'bodega', width: 14 },
      { header: 'Total', key: 'total', width: 14 },
    ];
    estiloHeader(porTurno.getRow(1), 'FF001529');
    reporte.por_turno.forEach((f) => {
      porTurno.addRow({ turno: etiquetaTurno(f.turno), kiosco: f.kiosco, bodega: f.bodega, total: f.total });
    });

    const porBodega = workbook.addWorksheet('Uso por bodega');
    porBodega.columns = [
      { header: 'Bodega', key: 'bodega_nombre', width: 28 },
      { header: 'Kiosco', key: 'kiosco', width: 14 },
      { header: 'Bodeguero', key: 'bodega', width: 14 },
      { header: 'Total', key: 'total', width: 14 },
    ];
    estiloHeader(porBodega.getRow(1));
    reporte.por_bodega.forEach((f) => {
      porBodega.addRow({ bodega_nombre: f.bodega_nombre, kiosco: f.kiosco, bodega: f.bodega, total: f.total });
    });

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    saveAs(blob, `NexoFaena_Uso_Kiosco_${Date.now()}.xlsx`);
  };

  return (
    <div className="reportes-wrapper">
      <h1 className="page-title"><FaDesktop /> Uso del Kiosco de Autoservicio</h1>
      <p className="page-subtitle">
        Cuántas entregas vienen del kiosco de autoservicio versus un bodeguero registrándolas a mano, día a día,
        por turno y por bodega — la radiografía de adopción del kiosco.
      </p>

      {error && (
        <div className="error-banner-reporte">
          <FaExclamationTriangle /> {error}
        </div>
      )}

      <form className="reportes-toolbar" onSubmit={handleBuscar}>
        <div className="filters-container">
          <div className="filter-group">
            <FaCalendarAlt className="filter-icon" />
            <input
              type="date"
              className="filter-input"
              value={filtros.fechaDesde}
              onChange={(e) => handleChange('fechaDesde', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <FaCalendarAlt className="filter-icon" />
            <input
              type="date"
              className="filter-input"
              value={filtros.fechaHasta}
              onChange={(e) => handleChange('fechaHasta', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <FaMapMarkerAlt className="filter-icon" />
            <select className="filter-input" value={filtros.bodega} onChange={(e) => handleChange('bodega', e.target.value)}>
              <option value="">Todas las bodegas</option>
              {bodegas.map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
            </select>
          </div>

          <button type="submit" className="btn-buscar-reporte" disabled={cargando}>
            <FaSearch /> {cargando ? 'Buscando...' : 'Buscar'}
          </button>
        </div>

        <div className="export-buttons-group">
          <button type="button" className="btn-export-excel" onClick={exportarExcel} disabled={cargando}>
            <FaFileExcel /> Exportar Excel
          </button>
        </div>
      </form>

      <div className="kpi-row-reporte">
        <div className="kpi-card-reporte">
          <FaChartBar className="kpi-icon-reporte" />
          <div>
            <div className="kpi-value-reporte">{reporte.resumen_general.total_entregas}</div>
            <div className="kpi-label-reporte">Entregas totales</div>
          </div>
        </div>

        <div className="kpi-card-reporte">
          <FaDesktop className="kpi-icon-reporte" />
          <div>
            <div className="kpi-value-reporte">{reporte.resumen_general.total_kiosco}</div>
            <div className="kpi-label-reporte">Vía kiosco</div>
          </div>
        </div>

        <div className="kpi-card-reporte">
          <FaUserTie className="kpi-icon-reporte" />
          <div>
            <div className="kpi-value-reporte">{reporte.resumen_general.total_bodega}</div>
            <div className="kpi-label-reporte">Vía bodeguero</div>
          </div>
        </div>

        <div className="kpi-card-reporte">
          <FaPercentage className="kpi-icon-reporte" />
          <div>
            <div className="kpi-value-reporte">{reporte.resumen_general.porcentaje_kiosco}%</div>
            <div className="kpi-label-reporte">Adopción del kiosco</div>
          </div>
        </div>
      </div>

      <div className="reportes-card">
        <div className="reportes-card-header">
          <FaChartBar /> Entregas por día ({reporte.por_dia.length} día(s) con movimiento)
        </div>

        <div className="chart-container-reporte">
          {reporte.por_dia.length === 0 ? (
            <div className="empty-state">Sin entregas registradas con estos filtros.</div>
          ) : (
            <Bar
              data={chartDataPorDia}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 14 } } },
                scales: {
                  y: { beginAtZero: true, stacked: true, grid: { color: 'rgba(255,255,255,0.08)' }, ticks: { precision: 0 } },
                  x: { stacked: true, grid: { display: false } },
                },
              }}
            />
          )}
        </div>
      </div>

      <div className="reportes-card">
        <div className="reportes-card-header">
          <FaBoxes /> Por turno
        </div>

        <div className="table-responsive">
          <table className="reportes-table">
            <thead>
              <tr>
                <th>Turno</th>
                <th className="text-center">Kiosco</th>
                <th className="text-center">Bodeguero</th>
                <th className="text-center">Total</th>
              </tr>
            </thead>
            <tbody>
              {cargando ? (
                <tr><td colSpan="4" className="loading-state">Cargando reporte...</td></tr>
              ) : reporte.por_turno.length === 0 ? (
                <tr><td colSpan="4" className="empty-state">Sin entregas registradas con estos filtros.</td></tr>
              ) : (
                reporte.por_turno.map((f) => (
                  <tr key={f.turno}>
                    <td>{etiquetaTurno(f.turno)}</td>
                    <td className="text-center">{f.kiosco}</td>
                    <td className="text-center">{f.bodega}</td>
                    <td className="text-center"><strong>{f.total}</strong></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="reportes-card">
        <div className="reportes-card-header">
          <FaMapMarkerAlt /> Por bodega
        </div>

        <div className="table-responsive">
          <table className="reportes-table">
            <thead>
              <tr>
                <th>Bodega</th>
                <th className="text-center">Kiosco</th>
                <th className="text-center">Bodeguero</th>
                <th className="text-center">Total</th>
              </tr>
            </thead>
            <tbody>
              {cargando ? (
                <tr><td colSpan="4" className="loading-state">Cargando reporte...</td></tr>
              ) : reporte.por_bodega.length === 0 ? (
                <tr><td colSpan="4" className="empty-state">Sin entregas registradas con estos filtros.</td></tr>
              ) : (
                reporte.por_bodega.map((f) => (
                  <tr key={f.bodega_id}>
                    <td>{f.bodega_nombre || 'Sin bodega'}</td>
                    <td className="text-center">{f.kiosco}</td>
                    <td className="text-center">{f.bodega}</td>
                    <td className="text-center"><strong>{f.total}</strong></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ReporteUsoKiosco;
