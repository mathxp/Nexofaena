import { useState, useEffect } from 'react';
import {
  FaExclamationCircle,
  FaCheckCircle,
  FaFileDownload,
  FaCircle,
  FaExclamationTriangle,
  FaBell,
  FaBoxOpen,
} from 'react-icons/fa';

import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import './Alertas.css';

const Alertas = () => {
  const [vistaActiva, setVistaActiva] = useState('STOCK');
  const [inventario, setInventario] = useState([]);
  const [alertasSistema, setAlertasSistema] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    cargarDatos();
  }, []);

  const cargarDatos = async () => {
    try {
      const [resInv, resSys] = await Promise.all([
        api.get('/inventario/'),
        api.get('/alertas/').catch(() => ({ data: [] })),
      ]);

      setInventario(Array.isArray(resInv.data) ? resInv.data : []);
      setAlertasSistema(Array.isArray(resSys.data) ? resSys.data : []);
      setError('');
    } catch {
      setError('Error al cargar la información del servidor.');
    }
  };

  const marcarComoLeida = async (id) => {
    try {
      await api.patch(`/alertas/${id}/`, { leida: true });
      cargarDatos();
    } catch {
      setError('Error al actualizar el estado de la alerta.');
    }
  };

  const stockCritico = inventario.filter(
    (i) => Number(i.stock_actual) < Number(i.stock_minimo)
  );

  const stockBajo = inventario.filter((i) => {
    const actual = Number(i.stock_actual);
    const minimo = Number(i.stock_minimo);
    return actual >= minimo && actual <= minimo * 1.2;
  });

  const stockOptimo = inventario.filter(
    (i) => Number(i.stock_actual) > Number(i.stock_minimo) * 1.2
  );

  const obtenerEstadoStock = (item) => {
    const actual = Number(item.stock_actual);
    const minimo = Number(item.stock_minimo);

    if (actual < minimo) return 'CRÍTICO';
    if (actual >= minimo && actual <= minimo * 1.2) return 'BAJO';
    return 'ÓPTIMO';
  };

  const generarExcelAlertas = async () => {
    const workbook = new ExcelJS.Workbook();
    workbook.creator = 'NexoFaena SGI';
    workbook.created = new Date();

    const resumen = workbook.addWorksheet('Resumen Ejecutivo', {
      views: [{ showGridLines: false }],
    });

    const alertas = workbook.addWorksheet('Alertas del Sistema', {
      views: [{ showGridLines: false }],
    });

    const stock = workbook.addWorksheet('Estado de Stock', {
      views: [{ showGridLines: false }],
    });

    const grafico = workbook.addWorksheet('Resumen Gráfico', {
      views: [{ showGridLines: false }],
    });

    const totalAlertas = alertasSistema.length;
    const alertasNoLeidas = alertasSistema.filter((a) => !a.leida).length;
    const alertasLeidas = alertasSistema.filter((a) => a.leida).length;

    const tipos = alertasSistema.reduce((acc, alerta) => {
      const tipo = alerta.tipo_alerta || 'SIN_TIPO';
      acc[tipo] = (acc[tipo] || 0) + 1;
      return acc;
    }, {});

    resumen.mergeCells('A1:F1');
    resumen.getCell('A1').value = 'NEXOFAENA SGI - REPORTE GENERAL DE ALERTAS';
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
    resumen.addRow(['Total alertas', totalAlertas]);
    resumen.addRow(['Alertas no leídas', alertasNoLeidas]);
    resumen.addRow(['Alertas leídas', alertasLeidas]);
    resumen.addRow(['Stock crítico', stockCritico.length]);
    resumen.addRow(['Stock bajo', stockBajo.length]);
    resumen.addRow(['Stock óptimo', stockOptimo.length]);

    resumen.columns = [
      { width: 28 },
      { width: 22 },
      { width: 20 },
      { width: 20 },
      { width: 20 },
      { width: 20 },
    ];

    resumen.eachRow((row, rowNumber) => {
      row.eachCell((cell) => {
        cell.border = {
          bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        };

        if (rowNumber >= 3) {
          cell.font = { bold: row.getCell(1) === cell };
          cell.alignment = { vertical: 'middle' };
        }
      });
    });

    alertas.columns = [
      { header: 'ID', key: 'id', width: 10 },
      { header: 'Fecha', key: 'fecha', width: 24 },
      { header: 'Tipo', key: 'tipo', width: 22 },
      { header: 'Producto', key: 'producto', width: 34 },
      { header: 'Código', key: 'codigo', width: 18 },
      { header: 'Bodega', key: 'bodega', width: 26 },
      { header: 'Mensaje', key: 'mensaje', width: 70 },
      { header: 'Estado', key: 'estado', width: 18 },
    ];

    alertas.getRow(1).eachCell((cell) => {
      cell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FFEA580C' },
      };
      cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
    });

    alertasSistema.forEach((a) => {
      const row = alertas.addRow({
        id: a.id,
        fecha: a.fecha_alerta ? new Date(a.fecha_alerta).toLocaleString() : 'N/A',
        tipo: a.tipo_alerta || 'N/A',
        producto: a.inventario_nombre || 'Sistema',
        codigo: a.inventario_codigo || 'N/A',
        bodega: a.bodega_nombre || 'N/A',
        mensaje: a.mensaje || 'Sin mensaje',
        estado: a.leida ? 'Leída' : 'Pendiente',
      });

      row.eachCell((cell) => {
        cell.alignment = { vertical: 'middle', wrapText: true };
        cell.border = {
          bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          left: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          right: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        };
      });

      const estadoCell = row.getCell(8);
      if (a.leida) {
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
          fgColor: { argb: 'FFFEE2E2' },
        };
        estadoCell.font = { bold: true, color: { argb: 'FF991B1B' } };
      }
    });

    alertas.autoFilter = {
      from: 'A1',
      to: 'H1',
    };

    stock.columns = [
      { header: 'ID', key: 'id', width: 10 },
      { header: 'Código', key: 'codigo', width: 18 },
      { header: 'Producto', key: 'producto', width: 34 },
      { header: 'Bodega', key: 'bodega', width: 26 },
      { header: 'Stock actual', key: 'actual', width: 16 },
      { header: 'Stock mínimo', key: 'minimo', width: 16 },
      { header: 'Stock máximo', key: 'maximo', width: 16 },
      { header: 'Estado', key: 'estado', width: 18 },
    ];

    stock.getRow(1).eachCell((cell) => {
      cell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FF001529' },
      };
      cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
    });

    inventario.forEach((item) => {
      const estado = obtenerEstadoStock(item);

      const row = stock.addRow({
        id: item.id,
        codigo: item.codigo || 'N/A',
        producto: item.nombre || 'Sin nombre',
        bodega: item.bodega_nombre || 'N/A',
        actual: Number(item.stock_actual || 0),
        minimo: Number(item.stock_minimo || 0),
        maximo: Number(item.stock_maximo || 0),
        estado,
      });

      row.eachCell((cell) => {
        cell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true };
        cell.border = {
          bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          left: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          right: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        };
      });

      const estadoCell = row.getCell(8);

      if (estado === 'CRÍTICO') {
        estadoCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFEE2E2' } };
        estadoCell.font = { bold: true, color: { argb: 'FF991B1B' } };
      } else if (estado === 'BAJO') {
        estadoCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFEF3C7' } };
        estadoCell.font = { bold: true, color: { argb: 'FF92400E' } };
      } else {
        estadoCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFD1FAE5' } };
        estadoCell.font = { bold: true, color: { argb: 'FF065F46' } };
      }
    });

    stock.autoFilter = {
      from: 'A1',
      to: 'H1',
    };

    grafico.columns = [
      { width: 28 },
      { width: 14 },
      { width: 50 },
    ];

    grafico.mergeCells('A1:C1');
    grafico.getCell('A1').value = 'RESUMEN GRÁFICO DE ALERTAS Y STOCK';
    grafico.getCell('A1').font = { bold: true, size: 15, color: { argb: 'FFFFFFFF' } };
    grafico.getCell('A1').fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF001529' },
    };
    grafico.getCell('A1').alignment = { horizontal: 'center' };

    const resumenGrafico = [
      ['Alertas no leídas', alertasNoLeidas, 'FFEF4444'],
      ['Alertas leídas', alertasLeidas, 'FF10B981'],
      ['Stock crítico', stockCritico.length, 'FFDC2626'],
      ['Stock bajo', stockBajo.length, 'FFF59E0B'],
      ['Stock óptimo', stockOptimo.length, 'FF10B981'],
      ...Object.entries(tipos).map(([tipo, total]) => [`Tipo: ${tipo}`, total, 'FF60A5FA']),
    ];

    grafico.addRow([]);
    grafico.addRow(['Indicador', 'Total', 'Barra visual']);

    grafico.getRow(3).eachCell((cell) => {
      cell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FFEA580C' },
      };
      cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      cell.alignment = { horizontal: 'center' };
    });

    const maxValue = Math.max(...resumenGrafico.map((r) => Number(r[1])), 1);

    resumenGrafico.forEach(([label, value, color]) => {
      const row = grafico.addRow([
        label,
        value,
        '█'.repeat(Math.max(1, Math.round((Number(value) / maxValue) * 25))),
      ]);

      row.getCell(3).font = {
        bold: true,
        color: { argb: color },
      };

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

    saveAs(blob, `NexoFaena_Alertas_Completo_${Date.now()}.xlsx`);
  };

  return (
    <div className="alertas-wrapper">
      <h1 className="page-title">
        <FaExclamationCircle /> Alertas de Stock
        <span className="title-sub">(PAÑOL / BODEGAS)</span>
      </h1>

      {error && (
        <div className="error-msg">
          <FaExclamationTriangle /> {error}
        </div>
      )}

      <div className="view-selector">
        <button
          className={`view-btn ${vistaActiva === 'STOCK' ? 'active' : ''}`}
          onClick={() => setVistaActiva('STOCK')}
        >
          <FaBoxOpen /> Estado de Insumos
        </button>

        <button
          className={`view-btn ${vistaActiva === 'SISTEMA' ? 'active' : ''}`}
          onClick={() => setVistaActiva('SISTEMA')}
        >
          <FaBell /> Notificaciones de Sistema
        </button>
      </div>

      <button className="btn-exportar" onClick={generarExcelAlertas}>
        <FaFileDownload /> EXPORTAR EXCEL COMPLETO DE ALERTAS
      </button>

      {vistaActiva === 'STOCK' ? (
        <>
          <div className="status-pills">
            <div className="pill pill-red">
              <FaCircle style={{ fontSize: '10px' }} /> CRÍTICO ({stockCritico.length})
            </div>

            <div className="pill pill-orange">
              <FaCircle style={{ fontSize: '10px' }} /> BAJO ({stockBajo.length})
            </div>

            <div className="pill pill-green">
              <FaCircle style={{ fontSize: '10px' }} /> OK ({stockOptimo.length})
            </div>
          </div>

          <div className="cards-grid">
            <div className="stock-card">
              <div className="card-header bg-red">
                <FaCircle style={{ fontSize: '12px' }} /> QUIEBRE DE STOCK
              </div>

              <div className="stock-list">
                {stockCritico.length === 0 ? (
                  <div className="item-empty">No hay insumos en quiebre.</div>
                ) : (
                  stockCritico.map((item) => (
                    <div key={item.id} className="stock-item">
                      <FaExclamationTriangle className="item-icon icon-red" />
                      <div className="item-details">
                        <div className="item-name">{item.nombre}</div>
                        <div className="item-stats">
                          Stock Actual: {item.stock_actual} | Mínimo: {item.stock_minimo}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="stock-card">
              <div className="card-header bg-orange">
                <FaCircle style={{ fontSize: '12px' }} /> STOCK BAJO
              </div>

              <div className="stock-list">
                {stockBajo.length === 0 ? (
                  <div className="item-empty">No hay insumos con stock bajo.</div>
                ) : (
                  stockBajo.map((item) => (
                    <div key={item.id} className="stock-item">
                      <FaExclamationTriangle className="item-icon icon-orange" />
                      <div className="item-details">
                        <div className="item-name">{item.nombre}</div>
                        <div className="item-stats">
                          Stock Actual: {item.stock_actual} | Mínimo: {item.stock_minimo}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="stock-card">
              <div className="card-header bg-green">
                <FaCircle style={{ fontSize: '12px' }} /> STOCK ÓPTIMO
              </div>

              <div className="stock-list">
                {stockOptimo.length === 0 ? (
                  <div className="item-empty">No hay insumos en estado óptimo.</div>
                ) : (
                  stockOptimo.slice(0, 4).map((item) => (
                    <div key={item.id} className="stock-item">
                      <FaCheckCircle className="item-icon icon-green" />
                      <div className="item-details">
                        <div className="item-name">{item.nombre}</div>
                        <div className="item-stats">
                          Stock Actual: {item.stock_actual} | Mínimo: {item.stock_minimo}
                        </div>
                      </div>
                    </div>
                  ))
                )}

                {stockOptimo.length > 4 && (
                  <div className="item-empty" style={{ color: '#10b981' }}>
                    + {stockOptimo.length - 4} insumos en estado óptimo
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="system-alerts-container">
          <table className="system-alerts-table">
            <thead>
              <tr>
                <th>Fecha y Hora</th>
                <th>Tipo</th>
                <th>Producto</th>
                <th>Bodega</th>
                <th>Mensaje</th>
                <th>Acción</th>
              </tr>
            </thead>

            <tbody>
              {alertasSistema.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                    No hay notificaciones de sistema.
                  </td>
                </tr>
              ) : (
                alertasSistema.map((alerta) => (
                  <tr key={alerta.id} className={alerta.leida ? 'row-read' : 'row-unread'}>
                    <td>{new Date(alerta.fecha_alerta).toLocaleString()}</td>
                    <td>{alerta.tipo_alerta}</td>
                    <td>{alerta.inventario_nombre || 'Sistema'}</td>
                    <td>{alerta.bodega_nombre || 'N/A'}</td>
                    <td>{alerta.mensaje}</td>
                    <td>
                      {!alerta.leida ? (
                        <button onClick={() => marcarComoLeida(alerta.id)} className="btn-mark-read">
                          Marcar Leída
                        </button>
                      ) : (
                        <span className="status-read">
                          <FaCheckCircle /> Leída
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Alertas;