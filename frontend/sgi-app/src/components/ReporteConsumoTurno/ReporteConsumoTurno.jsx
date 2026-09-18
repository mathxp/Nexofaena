import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  FaUserClock,
  FaSearch,
  FaCalendarAlt,
  FaFilter,
  FaIdCard,
  FaFileExcel,
  FaExclamationTriangle,
  FaWifi,
  FaUsers,
  FaBoxes,
  FaChartBar,
  FaFlag,
} from 'react-icons/fa';

import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import { db } from '../../db';
import './ReporteConsumoTurno.css';

const CLAVE_CACHE = 'epp_por_turno';

const fechaISO = (date) => date.toISOString().slice(0, 10);

const filtrosPorDefecto = () => {
  const hoy = new Date();
  const hace30Dias = new Date();
  hace30Dias.setDate(hoy.getDate() - 30);

  return {
    fechaDesde: fechaISO(hace30Dias),
    fechaHasta: fechaISO(hoy),
    rut: '',
    turno: '',
    producto: '',
  };
};

const reporteVacio = {
  periodo: { fecha_desde: '', fecha_hasta: '' },
  filas: [],
  resumen_por_trabajador: [],
  resumen_general: { total_unidades: 0, trabajadores_evaluados: 0, promedio_por_trabajador: 0 },
  casos_revisar_historico: [],
};

const ReporteConsumoTurno = () => {
  const [filtros, setFiltros] = useState(filtrosPorDefecto);
  const [reporte, setReporte] = useState(reporteVacio);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [offline, setOffline] = useState(false);
  const [sincronizadoEn, setSincronizadoEn] = useState(null);

  const role = localStorage.getItem('user_role') || '';
  const esAdministrador = role === 'Administrador';

  const cargarReporte = useCallback(async (filtrosActuales) => {
    setCargando(true);
    setError('');

    const params = {
      fecha_desde: filtrosActuales.fechaDesde,
      fecha_hasta: filtrosActuales.fechaHasta,
    };
    if (filtrosActuales.rut.trim()) params.rut = filtrosActuales.rut.trim();
    if (filtrosActuales.turno) params.turno = filtrosActuales.turno;
    if (filtrosActuales.producto.trim()) params.producto = filtrosActuales.producto.trim();

    try {
      const res = await api.get('/reportes/epp-por-turno/', { params });
      const ahora = new Date().toISOString();

      setReporte({ ...reporteVacio, ...res.data });
      setOffline(false);
      setSincronizadoEn(ahora);

      try {
        await db.cache_reportes.put({ clave: CLAVE_CACHE, data: res.data, sincronizado_en: ahora });
      } catch {
        // Cache local best-effort: si falla (ej. modo privado), no bloquea la vista.
      }
    } catch (err) {
      console.error(err);

      try {
        const cache = await db.cache_reportes.get(CLAVE_CACHE);

        if (cache) {
          setReporte({ ...reporteVacio, ...cache.data });
          setOffline(true);
          setSincronizadoEn(cache.sincronizado_en);
        } else {
          setError('No se pudo generar el reporte y no hay un dato local sincronizado todavía.');
        }
      } catch {
        setError('No se pudo generar el reporte. Verifica tu conexión.');
      }
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
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

  const etiquetaTurno = (turno) => (turno === 'dia' ? 'Día' : turno === 'noche' ? 'Noche' : turno);

  // Agrupa visualmente las filas consecutivas de un mismo trabajador+turno
  // (el backend ya las entrega contiguas, ordenadas por trabajador y turno)
  // para no repetir su nombre/cargo/turno en cada producto que retiró: se
  // combinan esas celdas con rowSpan y solo cambia la fila por producto.
  const filasAgrupadas = useMemo(() => {
    const filas = reporte.filas;
    const agrupadas = [];
    let i = 0;

    while (i < filas.length) {
      const actual = filas[i];
      let tamanoGrupo = 1;

      while (
        i + tamanoGrupo < filas.length &&
        filas[i + tamanoGrupo].trabajador_id === actual.trabajador_id &&
        filas[i + tamanoGrupo].turno === actual.turno
      ) {
        tamanoGrupo += 1;
      }

      for (let j = 0; j < tamanoGrupo; j += 1) {
        agrupadas.push({
          ...filas[i + j],
          _inicioGrupo: j === 0,
          _tamanoGrupo: tamanoGrupo,
        });
      }

      i += tamanoGrupo;
    }

    return agrupadas;
  }, [reporte.filas]);

  const exportarExcel = async () => {
    if (reporte.filas.length === 0) {
      alert('No hay datos para exportar con estos filtros.');
      return;
    }

    const workbook = new ExcelJS.Workbook();
    workbook.creator = 'NexoFaena SGI';
    workbook.created = new Date();

    const columnasBase = [
      { header: 'Trabajador', key: 'trabajador', width: 30 },
      ...(esAdministrador ? [{ header: 'RUT', key: 'rut', width: 16 }] : []),
      { header: 'Cargo', key: 'cargo', width: 24 },
      { header: 'Turno', key: 'turno', width: 12 },
      { header: 'Producto', key: 'producto', width: 30 },
      { header: 'Cantidad', key: 'cantidad', width: 14 },
      { header: 'Promedio del grupo', key: 'promedio', width: 18 },
      { header: 'Estado', key: 'estado', width: 18 },
    ];

    const detalle = workbook.addWorksheet('Consumo por Turno');
    detalle.columns = columnasBase;
    detalle.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
    detalle.getRow(1).eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEA580C' } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
    });

    reporte.filas.forEach((f) => {
      detalle.addRow({
        trabajador: f.trabajador_nombre,
        rut: f.rut,
        cargo: f.cargo,
        turno: etiquetaTurno(f.turno),
        producto: f.producto_nombre,
        cantidad: f.cantidad,
        promedio: f.promedio_cuadrilla,
        estado: f.estado_revision === 'revisar' ? 'Fuera del promedio' : 'Normal',
      });
    });

    const revisar = workbook.addWorksheet('Casos a Revisar (histórico)');
    revisar.columns = [
      { header: 'Trabajador', key: 'trabajador', width: 30 },
      ...(esAdministrador ? [{ header: 'RUT', key: 'rut', width: 16 }] : []),
      { header: 'Producto', key: 'producto', width: 30 },
      { header: 'Promedio del período', key: 'periodo', width: 20 },
      { header: 'Promedio histórico propio', key: 'historico', width: 22 },
      { header: 'Z-score', key: 'z', width: 12 },
    ];
    revisar.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
    revisar.getRow(1).eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF001529' } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
    });

    reporte.casos_revisar_historico.forEach((c) => {
      revisar.addRow({
        trabajador: c.trabajador_nombre,
        rut: c.rut,
        producto: c.producto_nombre,
        periodo: c.promedio_periodo,
        historico: c.promedio_historico,
        z: c.z_score,
      });
    });

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    saveAs(blob, `NexoFaena_Consumo_EPP_Turno_${Date.now()}.xlsx`);
  };

  return (
    <div className="reportes-wrapper">
      <h1 className="page-title"><FaUserClock /> Consumo de EPP por Trabajador y Turno</h1>
      <p className="page-subtitle">
        Radiografía de lo entregado por el pañol: cuánto retira cada trabajador, en qué turno, y cómo se compara
        contra el promedio de su cuadrilla.
      </p>

      {offline && (
        <div className="offline-banner">
          <FaWifi /> Sin conexión: mostrando el último reporte sincronizado
          {sincronizadoEn && ` (${new Date(sincronizadoEn).toLocaleString()})`}.
        </div>
      )}

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
            <FaIdCard className="filter-icon" />
            <input
              type="text"
              className="filter-input"
              placeholder="RUT trabajador..."
              value={filtros.rut}
              onChange={(e) => handleChange('rut', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <FaFilter className="filter-icon" />
            <select
              className="filter-input"
              value={filtros.turno}
              onChange={(e) => handleChange('turno', e.target.value)}
            >
              <option value="">Todos los turnos</option>
              <option value="dia">Día</option>
              <option value="noche">Noche</option>
            </select>
          </div>

          <div className="filter-group">
            <FaBoxes className="filter-icon" />
            <input
              type="text"
              className="filter-input"
              placeholder="Producto (ej. casco)..."
              value={filtros.producto}
              onChange={(e) => handleChange('producto', e.target.value)}
            />
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
          <FaUsers className="kpi-icon-reporte" />
          <div>
            <div className="kpi-value-reporte">{reporte.resumen_general.trabajadores_evaluados}</div>
            <div className="kpi-label-reporte">Trabajadores evaluados</div>
          </div>
        </div>

        <div className="kpi-card-reporte">
          <FaChartBar className="kpi-icon-reporte" />
          <div>
            <div className="kpi-value-reporte">{reporte.resumen_general.total_unidades}</div>
            <div className="kpi-label-reporte">Unidades totales entregadas</div>
          </div>
        </div>

        <div className="kpi-card-reporte">
          <FaBoxes className="kpi-icon-reporte" />
          <div>
            <div className="kpi-value-reporte">{reporte.resumen_general.promedio_por_trabajador}</div>
            <div className="kpi-label-reporte">Promedio por trabajador</div>
          </div>
        </div>
      </div>

      <div className="reportes-card">
        <div className="reportes-card-header">
          <FaFilter /> Detalle por trabajador y turno ({reporte.filas.length} registros)
        </div>

        <div className="table-responsive">
          <table className="reportes-table">
            <thead>
              <tr>
                <th>Trabajador</th>
                <th>Turno</th>
                <th>Producto</th>
                <th className="text-center">Cantidad</th>
                <th className="text-center">Promedio del grupo</th>
                <th className="text-center">Estado</th>
              </tr>
            </thead>

            <tbody>
              {cargando ? (
                <tr><td colSpan="6" className="loading-state">Cargando reporte...</td></tr>
              ) : reporte.filas.length === 0 ? (
                <tr><td colSpan="6" className="empty-state">Sin entregas registradas con estos filtros.</td></tr>
              ) : (
                filasAgrupadas.map((f, idx) => (
                  <tr
                    key={idx}
                    className={[
                      f.estado_revision === 'revisar' ? 'fila-fuera-promedio' : '',
                      f._inicioGrupo ? 'fila-inicio-grupo' : '',
                    ].join(' ').trim()}
                  >
                    {f._inicioGrupo && (
                      <>
                        <td rowSpan={f._tamanoGrupo}>
                          {f.trabajador_nombre}
                          <div className="ml-table-subtext">{f.cargo}</div>
                        </td>
                        <td rowSpan={f._tamanoGrupo}>{etiquetaTurno(f.turno)}</td>
                      </>
                    )}
                    <td>{f.producto_nombre}</td>
                    <td className="text-center">{f.cantidad}</td>
                    <td className="text-center">{f.promedio_cuadrilla}</td>
                    <td className="text-center">
                      {f.estado_revision === 'revisar' ? (
                        <span className="badge-revisar"><FaFlag /> Fuera del promedio</span>
                      ) : (
                        <span className="badge-normal">Normal</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="reportes-card casos-revisar-card">
        <div className="reportes-card-header">
          <FaExclamationTriangle /> Casos a revisar según historial propio ({reporte.casos_revisar_historico.length})
        </div>

        <p className="casos-revisar-desc">
          Compara a cada trabajador contra su propio promedio histórico, no contra el resto del equipo. Es
          informativo: ningún caso queda bloqueado ni se etiqueta como sospechoso, solo se marca para revisar.
        </p>

        {reporte.casos_revisar_historico.length === 0 ? (
          <div className="empty-state">Sin desviaciones relevantes respecto del historial propio en este período.</div>
        ) : (
          <div className="table-responsive">
            <table className="reportes-table">
              <thead>
                <tr>
                  <th>Trabajador</th>
                  <th>Producto</th>
                  <th className="text-center">Promedio del período</th>
                  <th className="text-center">Promedio histórico propio</th>
                  <th className="text-center">Z-score</th>
                </tr>
              </thead>
              <tbody>
                {reporte.casos_revisar_historico.map((c, idx) => (
                  <tr key={idx} className="fila-fuera-promedio">
                    <td>
                      {c.trabajador_nombre}
                      <div className="ml-table-subtext">{c.cargo}</div>
                    </td>
                    <td>{c.producto_nombre}</td>
                    <td className="text-center">{c.promedio_periodo}</td>
                    <td className="text-center">{c.promedio_historico}</td>
                    <td className="text-center">
                      <span className="badge-revisar"><FaFlag /> {c.z_score}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
};

export default ReporteConsumoTurno;
