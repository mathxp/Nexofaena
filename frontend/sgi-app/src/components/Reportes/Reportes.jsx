import { useState, useEffect } from 'react';
import {
  FaFilePdf,
  FaFileExcel,
  FaSearch,
  FaFilter,
  FaCalendarAlt,
  FaMapMarkerAlt,
  FaChevronLeft,
  FaChevronRight,
  FaSyncAlt,
  FaHourglassHalf,
  FaTools,
  FaUserClock,
} from 'react-icons/fa';

import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import ReporteConsumoTurno from '../ReporteConsumoTurno/ReporteConsumoTurno';
import './Reportes.css';

const REGISTROS_POR_PAGINA = 15;

const ReporteEntregas = () => {
  const [entregas, setEntregas] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const [filtroMes, setFiltroMes] = useState('');
  const [filtroTexto, setFiltroTexto] = useState('');
  const [filtroBodega, setFiltroBodega] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');
  const [paginaActual, setPaginaActual] = useState(1);

  useEffect(() => {
    cargarDatos();
  }, []);

  useEffect(() => {
    setPaginaActual(1);
  }, [filtroMes, filtroTexto, filtroBodega, filtroEstado]);

  const cargarDatos = async () => {
    try {
      setCargando(true);
      setError('');

      const [resEntregas, resBodegas] = await Promise.all([
        api.get('/entregas-epp/'),
        api.get('/bodegas/').catch(() => ({ data: [] })),
      ]);

      setEntregas(Array.isArray(resEntregas.data) ? resEntregas.data : []);
      setBodegas(Array.isArray(resBodegas.data) ? resBodegas.data : []);
    } catch (err) {
      console.error(err);
      setError('Error al cargar las entregas.');
    } finally {
      setCargando(false);
    }
  };

  const obtenerProductos = (entrega) => {
    if (!entrega.detalles || entrega.detalles.length === 0) return 'Sin productos';

    return entrega.detalles
      .map((d) => `${d.producto_nombre || 'Producto'} (${d.cantidad})`)
      .join(', ');
  };

  const obtenerCantidadTotal = (entrega) => {
    if (!entrega.detalles || entrega.detalles.length === 0) return 0;

    return entrega.detalles.reduce(
      (total, item) => total + Number(item.cantidad || 0),
      0
    );
  };

  const tienePendienteDevolucion = (entrega) =>
    (entrega.detalles || []).some((d) => d.es_devolutivo && !d.devuelto);

  const tieneVencimientoProximo = (entrega) =>
    (entrega.detalles || []).some(
      (d) => d.dias_para_vencer !== null && d.dias_para_vencer !== undefined && d.dias_para_vencer <= 30
    );

  const entregasFiltradas = entregas.filter((entrega) => {
    const texto = filtroTexto.toLowerCase();

    const trabajador = entrega.trabajador_nombre || '';
    const rut = entrega.trabajador_rut || '';
    const bodega = entrega.bodega_nombre || '';
    const responsable = entrega.usuario_nombre || '';
    const productos = obtenerProductos(entrega);

    const coincideTexto =
      trabajador.toLowerCase().includes(texto) ||
      rut.toLowerCase().includes(texto) ||
      bodega.toLowerCase().includes(texto) ||
      responsable.toLowerCase().includes(texto) ||
      productos.toLowerCase().includes(texto);

    let coincideMes = true;

    if (filtroMes && entrega.fecha_entrega) {
      const fecha = new Date(entrega.fecha_entrega);
      const mesEntrega = `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}`;
      coincideMes = mesEntrega === filtroMes;
    }

    const coincideBodega = filtroBodega ? String(entrega.bodega) === String(filtroBodega) : true;
    const coincideEstado = filtroEstado ? entrega.estado === filtroEstado : true;

    return coincideTexto && coincideMes && coincideBodega && coincideEstado;
  });

  const totalPaginas = Math.max(1, Math.ceil(entregasFiltradas.length / REGISTROS_POR_PAGINA));
  const paginaSegura = Math.min(paginaActual, totalPaginas);
  const entregasPagina = entregasFiltradas.slice(
    (paginaSegura - 1) * REGISTROS_POR_PAGINA,
    paginaSegura * REGISTROS_POR_PAGINA
  );

  const generarPDF = () => {
    if (entregasFiltradas.length === 0) {
      alert('No hay datos para exportar.');
      return;
    }

    const doc = new jsPDF('landscape');

    doc.setFillColor(0, 21, 41);
    doc.rect(0, 0, 297, 26, 'F');

    doc.setTextColor(255, 255, 255);
    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.text('NEXOFAENA SGI', 14, 11);

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.text('Reporte Oficial de Entregas de EPP', 14, 18);

    doc.setFontSize(8);
    doc.text(`Generado: ${new Date().toLocaleString()}`, 210, 18);

    const columnas = [
      'ID',
      'Trabajador',
      'RUT',
      'Bodega',
      'Responsable',
      'Productos',
      'Cantidad',
      'Fecha',
      'Estado',
      'Pend. Devolución',
      'Vence Pronto',
    ];

    const filas = entregasFiltradas.map((e) => [
      e.id,
      e.trabajador_nombre || 'No registrado',
      e.trabajador_rut || 'N/A',
      e.bodega_nombre || 'N/A',
      e.usuario_nombre || 'N/A',
      obtenerProductos(e),
      obtenerCantidadTotal(e),
      e.fecha_entrega ? new Date(e.fecha_entrega).toLocaleString() : 'N/A',
      e.estado || 'COMPLETADA',
      tienePendienteDevolucion(e) ? 'Sí' : 'No',
      tieneVencimientoProximo(e) ? 'Sí' : 'No',
    ]);

    autoTable(doc, {
      head: [columnas],
      body: filas,
      startY: 34,
      theme: 'grid',
      headStyles: {
        fillColor: [234, 88, 12],
        textColor: [255, 255, 255],
        fontStyle: 'bold',
      },
      styles: {
        fontSize: 7.5,
        cellPadding: 3,
      },
      columnStyles: {
        5: { cellWidth: 60 },
      },
    });

    doc.save(`Reporte_Entregas_NexoFaena_${Date.now()}.pdf`);
  };

  const generarExcel = async () => {
    if (entregasFiltradas.length === 0) {
      alert('No hay datos para exportar.');
      return;
    }

    const workbook = new ExcelJS.Workbook();
    workbook.creator = 'NexoFaena SGI';
    workbook.created = new Date();

    const worksheet = workbook.addWorksheet('Entregas EPP', {
      views: [{ showGridLines: false }],
    });

    worksheet.mergeCells('A1:K1');
    const titleCell = worksheet.getCell('A1');
    titleCell.value = 'NEXOFAENA SGI - REPORTE DE ENTREGAS DE EPP';
    titleCell.font = { bold: true, size: 16, color: { argb: 'FFFFFFFF' } };
    titleCell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF001529' },
    };
    titleCell.alignment = { horizontal: 'center', vertical: 'middle' };
    worksheet.getRow(1).height = 28;

    worksheet.mergeCells('A2:K2');
    const subtitleCell = worksheet.getCell('A2');
    subtitleCell.value = `Generado: ${new Date().toLocaleString()} | Registros: ${entregasFiltradas.length}`;
    subtitleCell.font = { italic: true, color: { argb: 'FF64748B' } };
    subtitleCell.alignment = { horizontal: 'center' };

    worksheet.columns = [
      { key: 'id', width: 12 },
      { key: 'trabajador', width: 32 },
      { key: 'rut', width: 18 },
      { key: 'bodega', width: 24 },
      { key: 'responsable', width: 22 },
      { key: 'productos', width: 55 },
      { key: 'cantidad', width: 14 },
      { key: 'fecha', width: 24 },
      { key: 'estado', width: 18 },
      { key: 'pendiente', width: 18 },
      { key: 'vencimiento', width: 16 },
    ];

    const headerRow = worksheet.getRow(4);
    headerRow.values = [
      'ID',
      'Trabajador',
      'RUT',
      'Bodega',
      'Responsable',
      'Productos',
      'Cantidad total',
      'Fecha',
      'Estado',
      'Pend. Devolución',
      'Vence Pronto',
    ];

    headerRow.height = 26;

    headerRow.eachCell((cell) => {
      cell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FFEA580C' },
      };
      cell.font = {
        bold: true,
        color: { argb: 'FFFFFFFF' },
      };
      cell.alignment = {
        horizontal: 'center',
        vertical: 'middle',
      };
      cell.border = {
        top: { style: 'thin', color: { argb: 'FF001529' } },
        bottom: { style: 'medium', color: { argb: 'FF001529' } },
      };
    });

    entregasFiltradas.forEach((e, index) => {
      const row = worksheet.addRow({
        id: e.id,
        trabajador: e.trabajador_nombre || 'No registrado',
        rut: e.trabajador_rut || 'N/A',
        bodega: e.bodega_nombre || 'N/A',
        responsable: e.usuario_nombre || 'N/A',
        productos: obtenerProductos(e),
        cantidad: obtenerCantidadTotal(e),
        fecha: e.fecha_entrega ? new Date(e.fecha_entrega).toLocaleString() : 'N/A',
        estado: e.estado || 'COMPLETADA',
        pendiente: tienePendienteDevolucion(e) ? 'Sí' : 'No',
        vencimiento: tieneVencimientoProximo(e) ? 'Sí' : 'No',
      });

      row.eachCell((cell) => {
        cell.alignment = {
          vertical: 'middle',
          horizontal: 'center',
          wrapText: true,
        };

        cell.border = {
          bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          left: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          right: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        };

        if (index % 2 === 0) {
          cell.fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFF9FAFB' },
          };
        }
      });

      const estadoCell = row.getCell(9);

      if ((e.estado || '').toUpperCase() === 'COMPLETADA') {
        estadoCell.fill = {
          type: 'pattern',
          pattern: 'solid',
          fgColor: { argb: 'FFD1FAE5' },
        };
        estadoCell.font = { bold: true, color: { argb: 'FF065F46' } };
      } else {
        estadoCell.fill = {
          type: 'pattern',
          pattern: 'solid',
          fgColor: { argb: 'FFFEF3C7' },
        };
        estadoCell.font = { bold: true, color: { argb: 'FF92400E' } };
      }
    });

    worksheet.autoFilter = {
      from: 'A4',
      to: 'K4',
    };

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    saveAs(blob, `NexoFaena_Reporte_Entregas_${Date.now()}.xlsx`);
  };

  return (
    <div className="reportes-wrapper">
      <div className="reportes-header">
        <div>
          <h1 className="page-title">Módulo de Reportes</h1>
          <p className="page-subtitle">Reporte completo de entregas de EPP por trabajador, bodega y fecha</p>
        </div>
      </div>

      <div className="reportes-toolbar">
        <div className="filters-container">
          <div className="filter-group">
            <FaSearch className="filter-icon" />
            <input
              type="text"
              className="filter-input"
              placeholder="Buscar por trabajador, RUT, bodega o producto..."
              value={filtroTexto}
              onChange={(e) => setFiltroTexto(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <FaCalendarAlt className="filter-icon" />
            <input
              type="month"
              className="filter-input"
              value={filtroMes}
              onChange={(e) => setFiltroMes(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <FaMapMarkerAlt className="filter-icon" />
            <select className="filter-input" value={filtroBodega} onChange={(e) => setFiltroBodega(e.target.value)}>
              <option value="">Todas las bodegas</option>
              {bodegas.map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
            </select>
          </div>

          <div className="filter-group">
            <FaFilter className="filter-icon" />
            <select className="filter-input" value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
              <option value="">Todos los estados</option>
              <option value="COMPLETADA">Completada</option>
              <option value="PENDIENTE">Pendiente</option>
              <option value="ANULADA">Anulada</option>
            </select>
          </div>
        </div>

        <div className="export-buttons-group">
          <button className="btn-export-pdf" onClick={generarPDF} disabled={cargando}>
            <FaFilePdf /> Exportar PDF
          </button>

          <button className="btn-export-excel" onClick={generarExcel} disabled={cargando}>
            <FaFileExcel /> Exportar Excel
          </button>
        </div>
      </div>

      <div className="reportes-card">
        <div className="reportes-card-header">
          <FaFilter /> Vista previa ({entregasFiltradas.length} registros)
        </div>

        {cargando ? (
          <div className="loading-state">Cargando registros...</div>
        ) : error ? (
          <div className="error-state">{error}</div>
        ) : (
          <>
            <div className="table-responsive">
              <table className="reportes-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Trabajador</th>
                    <th>RUT</th>
                    <th>Bodega</th>
                    <th>Productos</th>
                    <th>Cantidad</th>
                    <th>Fecha</th>
                    <th>Estado</th>
                    <th>Indicadores</th>
                  </tr>
                </thead>

                <tbody>
                  {entregasPagina.length > 0 ? (
                    entregasPagina.map((e) => {
                      const pendiente = tienePendienteDevolucion(e);
                      const vencimiento = tieneVencimientoProximo(e);

                      return (
                        <tr key={e.id}>
                          <td><strong>#{e.id}</strong></td>
                          <td>{e.trabajador_nombre || 'No registrado'}</td>
                          <td>{e.trabajador_rut || 'N/A'}</td>
                          <td>{e.bodega_nombre || 'N/A'}</td>
                          <td>{obtenerProductos(e)}</td>
                          <td>{obtenerCantidadTotal(e)}</td>
                          <td>{e.fecha_entrega ? new Date(e.fecha_entrega).toLocaleDateString() : 'N/A'}</td>
                          <td>
                            <span className={`estado-etiqueta ${e.estado === 'COMPLETADA' ? 'estado-ok' : 'estado-pendiente'}`}>
                              {e.estado || 'COMPLETADA'}
                            </span>
                          </td>
                          <td>
                            <div className="indicadores-cell">
                              {pendiente && (
                                <span className="tag-pendiente"><FaSyncAlt /> Por devolver</span>
                              )}
                              {vencimiento && (
                                <span className="tag-vencimiento"><FaHourglassHalf /> Vence pronto</span>
                              )}
                              {!pendiente && !vencimiento && <span className="tag-ninguno">—</span>}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan="9" className="empty-state">
                        No se encontraron entregas con estos filtros.
                      </td>
                    </tr>
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
          </>
        )}
      </div>
    </div>
  );
};

const Reportes = () => {
  const [tab, setTab] = useState('entregas');

  return (
    <div className="reportes-page">
      <div className="reportes-tabs">
        <button
          className={`reportes-tab ${tab === 'entregas' ? 'active' : ''}`}
          onClick={() => setTab('entregas')}
        >
          <FaTools /> Entregas EPP
        </button>
        <button
          className={`reportes-tab ${tab === 'turno' ? 'active' : ''}`}
          onClick={() => setTab('turno')}
        >
          <FaUserClock /> Consumo por Turno
        </button>
      </div>

      {tab === 'entregas' ? <ReporteEntregas /> : <ReporteConsumoTurno />}
    </div>
  );
};

export default Reportes;
