import { useState, useEffect } from 'react';
import {
  FaExclamationCircle,
  FaCheckCircle,
  FaFileDownload,
  FaCircle,
  FaExclamationTriangle,
  FaBell,
  FaBoxOpen,
  FaChevronLeft,
  FaChevronRight,
  FaCheckDouble,
  FaTelegram,
  FaCopy,
} from 'react-icons/fa';

import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import './Alertas.css';

const ALERTAS_POR_PAGINA = 12;

// Misma clasificación que usa el backend (Inventario.necesita_reposicion /
// DashboardService.obtener_stock_estado), para que Alertas y el Dashboard
// Gerencial nunca se contradigan sobre qué es "bajo" o "crítico".
const clasificarStock = (item) => {
  const actual = Number(item.stock_actual);
  const minimo = Number(item.stock_minimo);
  const maximo = Number(item.stock_maximo);

  if (actual < minimo) return 'CRITICO';
  if (actual === minimo) return 'BAJO';
  if (maximo > 0 && actual > maximo) return 'SOBRE_STOCK';
  return 'OPTIMO';
};

const TIPOS_URGENTES = ['STOCK_CRITICO', 'VENCIMIENTO', 'CIERRE_TURNO'];
const TIPOS_AVISO = ['STOCK_BAJO', 'ANOMALIA_CONSUMO', 'MANTENIMIENTO'];

const badgeParaTipo = (tipo) => {
  if (TIPOS_URGENTES.includes(tipo)) return 'urgente';
  if (TIPOS_AVISO.includes(tipo)) return 'aviso';
  return 'info';
};

const Alertas = () => {
  const [vistaActiva, setVistaActiva] = useState('STOCK');
  const [inventario, setInventario] = useState([]);
  const [alertasSistema, setAlertasSistema] = useState([]);
  const [error, setError] = useState('');

  const [filtroTipo, setFiltroTipo] = useState('');
  const [filtroTexto, setFiltroTexto] = useState('');
  const [paginaActual, setPaginaActual] = useState(1);

  const [telegramEstado, setTelegramEstado] = useState(null);
  const [telegramCodigo, setTelegramCodigo] = useState(null);
  const [telegramCargando, setTelegramCargando] = useState(false);
  const [telegramError, setTelegramError] = useState('');

  useEffect(() => {
    cargarDatos();
    cargarEstadoTelegram();
  }, []);

  useEffect(() => { setPaginaActual(1); }, [filtroTipo, filtroTexto]);

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

  const cargarEstadoTelegram = async () => {
    try {
      const res = await api.get('/telegram/estado/');
      setTelegramEstado(res.data);
    } catch {
      // No es crítico para la pantalla de Alertas: si falla, simplemente no
      // se muestra el widget de vinculación.
    }
  };

  const generarCodigoTelegram = async () => {
    setTelegramCargando(true);
    setTelegramError('');

    try {
      const res = await api.post('/telegram/generar-codigo/');
      setTelegramCodigo(res.data);
    } catch (err) {
      setTelegramError(err.response?.data?.detail || 'No se pudo generar el código de vinculación.');
    } finally {
      setTelegramCargando(false);
    }
  };

  const copiarComandoTelegram = () => {
    if (!telegramCodigo) return;
    navigator.clipboard?.writeText(`/vincular ${telegramCodigo.codigo}`);
  };

  const marcarComoLeida = async (id) => {
    try {
      await api.patch(`/alertas/${id}/`, { leida: true });
      cargarDatos();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al actualizar el estado de la alerta.');
    }
  };

  const marcarTodasComoLeidas = async () => {
    const pendientes = alertasFiltradas.filter((a) => !a.leida);
    if (pendientes.length === 0) return;

    if (!window.confirm(`¿Marcar ${pendientes.length} alerta(s) como leídas?`)) return;

    try {
      await Promise.all(pendientes.map((a) => api.patch(`/alertas/${a.id}/`, { leida: true })));
      cargarDatos();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al marcar las alertas como leídas.');
    }
  };

  const stockCritico = inventario.filter((i) => clasificarStock(i) === 'CRITICO');
  const stockBajo = inventario.filter((i) => clasificarStock(i) === 'BAJO');
  const stockOptimo = inventario.filter((i) => clasificarStock(i) === 'OPTIMO');
  const stockSobre = inventario.filter((i) => clasificarStock(i) === 'SOBRE_STOCK');

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
    resumen.addRow(['Sobre stock', stockSobre.length]);

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

    const etiquetaEstado = {
      CRITICO: 'CRÍTICO',
      BAJO: 'BAJO',
      OPTIMO: 'ÓPTIMO',
      SOBRE_STOCK: 'SOBRE STOCK',
    };

    inventario.forEach((item) => {
      const estado = clasificarStock(item);

      const row = stock.addRow({
        id: item.id,
        codigo: item.codigo || 'N/A',
        producto: item.nombre || 'Sin nombre',
        bodega: item.bodega_nombre || 'N/A',
        actual: Number(item.stock_actual || 0),
        minimo: Number(item.stock_minimo || 0),
        maximo: Number(item.stock_maximo || 0),
        estado: etiquetaEstado[estado],
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

      if (estado === 'CRITICO') {
        estadoCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFEE2E2' } };
        estadoCell.font = { bold: true, color: { argb: 'FF991B1B' } };
      } else if (estado === 'BAJO' || estado === 'SOBRE_STOCK') {
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
      ['Sobre stock', stockSobre.length, 'FF60A5FA'],
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

  const texto = filtroTexto.toLowerCase();

  const alertasFiltradas = alertasSistema.filter((a) => {
    const coincideTipo = filtroTipo ? a.tipo_alerta === filtroTipo : true;
    const coincideTexto = texto
      ? (a.mensaje || '').toLowerCase().includes(texto) ||
        (a.inventario_nombre || '').toLowerCase().includes(texto) ||
        (a.bodega_nombre || '').toLowerCase().includes(texto)
      : true;

    return coincideTipo && coincideTexto;
  });

  const totalPaginas = Math.max(1, Math.ceil(alertasFiltradas.length / ALERTAS_POR_PAGINA));
  const paginaSegura = Math.min(paginaActual, totalPaginas);
  const alertasPagina = alertasFiltradas.slice(
    (paginaSegura - 1) * ALERTAS_POR_PAGINA,
    paginaSegura * ALERTAS_POR_PAGINA
  );

  const noLeidasFiltradas = alertasFiltradas.filter((a) => !a.leida).length;

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

      <div className="telegram-widget">
        <div className="telegram-widget-header">
          <FaTelegram />
          <span>Bot de Telegram</span>
        </div>

        {telegramEstado?.vinculado ? (
          <div className="telegram-widget-body">
            <FaCheckCircle className="icon-green" />
            <span>
              Vinculado{telegramEstado.telegram_username ? ` como @${telegramEstado.telegram_username}` : ''}.
              Escríbele por privado: /alertas, /stock, /historial, /atender.
            </span>
          </div>
        ) : telegramCodigo ? (
          <div className="telegram-widget-body telegram-widget-codigo">
            <span>
              Abre un chat privado con el bot y envíale exactamente:
            </span>
            <div className="telegram-codigo-linea">
              <code>/vincular {telegramCodigo.codigo}</code>
              <button type="button" onClick={copiarComandoTelegram} title="Copiar comando">
                <FaCopy />
              </button>
            </div>
            {telegramCodigo.deep_link && (
              <a href={telegramCodigo.deep_link} target="_blank" rel="noreferrer" className="telegram-deep-link">
                Abrir chat con el bot <FaTelegram />
              </a>
            )}
            <span className="telegram-codigo-expira">
              Válido hasta las {new Date(telegramCodigo.expira_en).toLocaleTimeString()}.
            </span>
          </div>
        ) : (
          <div className="telegram-widget-body">
            <span>Consulta stock, alertas y entregas, o marca alertas como atendidas, directo desde Telegram.</span>
            <button
              type="button"
              className="btn-vincular-telegram"
              onClick={generarCodigoTelegram}
              disabled={telegramCargando}
            >
              {telegramCargando ? 'Generando...' : 'Vincular mi Telegram'}
            </button>
          </div>
        )}

        {telegramError && <div className="error-msg" style={{ marginTop: '8px' }}>{telegramError}</div>}
      </div>

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

            <div className="pill pill-blue">
              <FaCircle style={{ fontSize: '10px' }} /> SOBRE STOCK ({stockSobre.length})
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
                  stockCritico.slice(0, 4).map((item) => (
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

                {stockCritico.length > 4 && (
                  <div className="item-empty" style={{ color: '#f87171' }}>
                    + {stockCritico.length - 4} insumos en quiebre
                  </div>
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
                  stockBajo.slice(0, 4).map((item) => (
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

                {stockBajo.length > 4 && (
                  <div className="item-empty" style={{ color: '#fbbf24' }}>
                    + {stockBajo.length - 4} insumos con stock bajo
                  </div>
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

            <div className="stock-card">
              <div className="card-header bg-blue">
                <FaCircle style={{ fontSize: '12px' }} /> SOBRE STOCK
              </div>

              <div className="stock-list">
                {stockSobre.length === 0 ? (
                  <div className="item-empty">No hay insumos sobre su stock máximo.</div>
                ) : (
                  stockSobre.slice(0, 4).map((item) => (
                    <div key={item.id} className="stock-item">
                      <FaExclamationTriangle className="item-icon icon-blue" />
                      <div className="item-details">
                        <div className="item-name">{item.nombre}</div>
                        <div className="item-stats">
                          Stock Actual: {item.stock_actual} | Máximo: {item.stock_maximo}
                        </div>
                      </div>
                    </div>
                  ))
                )}

                {stockSobre.length > 4 && (
                  <div className="item-empty" style={{ color: '#60a5fa' }}>
                    + {stockSobre.length - 4} insumos sobre stock
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="filtros-alertas">
            <select className="filtro-select" value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
              <option value="">Todos los tipos</option>
              <option value="STOCK_CRITICO">Stock Crítico</option>
              <option value="STOCK_BAJO">Stock Bajo</option>
              <option value="VENCIMIENTO">Vencimiento</option>
              <option value="ANOMALIA_CONSUMO">Anomalía de Consumo</option>
              <option value="MANTENIMIENTO">Mantenimiento</option>
              <option value="CIERRE_TURNO">Cierre de Turno</option>
              <option value="SISTEMA">Sistema</option>
            </select>

            <input
              type="text"
              className="filtro-texto"
              placeholder="Buscar por producto, bodega o mensaje..."
              value={filtroTexto}
              onChange={(e) => setFiltroTexto(e.target.value)}
            />

            <button
              className="btn-marcar-todas"
              onClick={marcarTodasComoLeidas}
              disabled={noLeidasFiltradas === 0}
            >
              <FaCheckDouble /> Marcar todas como leídas {noLeidasFiltradas > 0 && `(${noLeidasFiltradas})`}
            </button>
          </div>

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
                {alertasPagina.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                      No hay notificaciones que coincidan con el filtro.
                    </td>
                  </tr>
                ) : (
                  alertasPagina.map((alerta) => (
                    <tr key={alerta.id} className={alerta.leida ? 'row-read' : 'row-unread'}>
                      <td>{new Date(alerta.fecha_alerta).toLocaleString()}</td>
                      <td>
                        <span className={`badge-tipo badge-${badgeParaTipo(alerta.tipo_alerta)}`}>
                          {alerta.tipo_alerta}
                        </span>
                      </td>
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
        </>
      )}
    </div>
  );
};

export default Alertas;
