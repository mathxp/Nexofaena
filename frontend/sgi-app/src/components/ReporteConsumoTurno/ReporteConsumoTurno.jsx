import { Fragment, useState, useEffect, useCallback } from 'react';
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
  FaFlag,
  FaSun,
  FaMoon,
  FaDoorOpen,
  FaChevronDown,
  FaChevronUp,
} from 'react-icons/fa';

import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import api from '../../api';
import { db } from '../../db';
import './ReporteConsumoTurno.css';

const CLAVE_CACHE = 'epp_por_turno';
const FILAS_INICIALES = 15;
const PRODUCTOS_EN_RESUMEN = 3;

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
  resumen_por_trabajador: [],
  por_turno: [],
  resumen_general: { total_unidades: 0, trabajadores_evaluados: 0, promedio_por_trabajador: 0, total_visitas: 0, a_revisar: 0 },
  casos_revisar_historico: [],
};

const etiquetaTurno = (turno) => (turno === 'noche' ? 'Noche' : 'Día');

const formatearNumero = (valor) => Number(valor || 0).toLocaleString('es-CL', { maximumFractionDigits: 1 });

const ReporteConsumoTurno = () => {
  const [filtros, setFiltros] = useState(filtrosPorDefecto);
  const [reporte, setReporte] = useState(reporteVacio);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [offline, setOffline] = useState(false);
  const [sincronizadoEn, setSincronizadoEn] = useState(null);
  const [verTodos, setVerTodos] = useState(false);
  const [expandido, setExpandido] = useState(null);

  const role = localStorage.getItem('user_role') || '';
  const esAdministrador = role === 'Administrador';

  const cargarReporte = useCallback(async (filtrosActuales) => {
    setCargando(true);
    setError('');
    setExpandido(null);

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

  const trabajadores = reporte.resumen_por_trabajador || [];
  const visibles = verTodos ? trabajadores : trabajadores.slice(0, FILAS_INICIALES);
  const general = reporte.resumen_general;

  const exportarExcel = async () => {
    if (trabajadores.length === 0) {
      alert('No hay datos para exportar con estos filtros.');
      return;
    }

    const workbook = new ExcelJS.Workbook();
    workbook.creator = 'NexoFaena SGI';
    workbook.created = new Date();

    const estiloEncabezado = (hoja, color = 'FF1F6FD1') => {
      hoja.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
      hoja.getRow(1).eachCell((cell) => {
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: color } };
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
      });
    };

    const columnaRut = esAdministrador ? [{ header: 'RUT', key: 'rut', width: 16 }] : [];

    const resumen = workbook.addWorksheet('Resumen por trabajador');
    resumen.columns = [
      { header: 'Trabajador', key: 'trabajador', width: 28 },
      ...columnaRut,
      { header: 'Cargo', key: 'cargo', width: 20 },
      { header: 'Turno principal', key: 'turno', width: 16 },
      { header: 'Unidades', key: 'unidades', width: 12 },
      { header: 'Visitas al pañol', key: 'visitas', width: 16 },
      { header: 'Unidades por visita', key: 'porVisita', width: 18 },
      { header: 'Promedio del cargo', key: 'promedioCargo', width: 18 },
      { header: 'Estado', key: 'estado', width: 14 },
    ];
    estiloEncabezado(resumen);
    trabajadores.forEach((t) => {
      resumen.addRow({
        trabajador: t.trabajador_nombre,
        rut: t.rut,
        cargo: t.cargo,
        turno: etiquetaTurno(t.turno_principal),
        unidades: t.total_unidades,
        visitas: t.num_visitas,
        porVisita: t.unidades_por_visita,
        promedioCargo: t.promedio_cargo,
        estado: t.estado_revision === 'revisar' ? 'Revisar' : 'Normal',
      });
    });

    const detalle = workbook.addWorksheet('Detalle por producto');
    detalle.columns = [
      { header: 'Trabajador', key: 'trabajador', width: 28 },
      ...columnaRut,
      { header: 'Cargo', key: 'cargo', width: 20 },
      { header: 'Producto', key: 'producto', width: 32 },
      { header: 'Unidades', key: 'cantidad', width: 12 },
    ];
    estiloEncabezado(detalle);
    trabajadores.forEach((t) => {
      t.desglose_por_producto.forEach((p) => {
        detalle.addRow({ trabajador: t.trabajador_nombre, rut: t.rut, cargo: t.cargo, producto: p.producto_nombre, cantidad: p.cantidad });
      });
    });

    const revisar = workbook.addWorksheet('Casos según historial propio');
    revisar.columns = [
      { header: 'Trabajador', key: 'trabajador', width: 28 },
      ...columnaRut,
      { header: 'Producto', key: 'producto', width: 30 },
      { header: 'Por visita (período)', key: 'periodo', width: 20 },
      { header: 'Por visita (habitual)', key: 'historico', width: 20 },
    ];
    estiloEncabezado(revisar, 'FF0F2647');
    reporte.casos_revisar_historico.forEach((c) => {
      revisar.addRow({
        trabajador: c.trabajador_nombre, rut: c.rut, producto: c.producto_nombre,
        periodo: c.promedio_periodo, historico: c.promedio_historico,
      });
    });

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, `NexoFaena_Consumo_EPP_Turno_${Date.now()}.xlsx`);
  };

  return (
    <div className="reportes-wrapper">
      <h1 className="page-title"><FaUserClock /> Consumo de EPP por Trabajador y Turno</h1>
      <p className="page-subtitle">
        Cuánto retira cada trabajador del pañol y cómo se compara con otros de su mismo cargo.
        Las radios no cuentan: se prestan y se devuelven.
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
              aria-label="Desde"
            />
          </div>

          <div className="filter-group">
            <FaCalendarAlt className="filter-icon" />
            <input
              type="date"
              className="filter-input"
              value={filtros.fechaHasta}
              onChange={(e) => handleChange('fechaHasta', e.target.value)}
              aria-label="Hasta"
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
              placeholder="Producto (ej. guantes)..."
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

      {/* ============ RESUMEN ============ */}
      <div className="rct-indicadores">
        <div className="rct-indicador">
          <FaUsers className="rct-indicador-icono" />
          <div>
            <div className="rct-indicador-valor">{general.trabajadores_evaluados}</div>
            <div className="rct-indicador-titulo">Trabajadores</div>
          </div>
        </div>
        <div className="rct-indicador">
          <FaBoxes className="rct-indicador-icono" />
          <div>
            <div className="rct-indicador-valor">{formatearNumero(general.total_unidades)}</div>
            <div className="rct-indicador-titulo">Unidades entregadas</div>
          </div>
        </div>
        <div className="rct-indicador">
          <FaDoorOpen className="rct-indicador-icono" />
          <div>
            <div className="rct-indicador-valor">{formatearNumero(general.total_visitas)}</div>
            <div className="rct-indicador-titulo">Visitas al pañol</div>
          </div>
        </div>
        <div className={`rct-indicador ${general.a_revisar > 0 ? 'rct-indicador-alerta' : ''}`}>
          <FaFlag className="rct-indicador-icono" />
          <div>
            <div className="rct-indicador-valor">{general.a_revisar}</div>
            <div className="rct-indicador-titulo">Para revisar</div>
          </div>
        </div>
      </div>

      {reporte.por_turno.length > 0 && (
        <div className="rct-turnos">
          {reporte.por_turno.map((t) => (
            <div key={t.turno} className={`rct-turno rct-turno-${t.turno}`}>
              <div className="rct-turno-nombre">
                {t.turno === 'noche' ? <FaMoon /> : <FaSun />} Turno {etiquetaTurno(t.turno).toLowerCase()}
              </div>
              <div className="rct-turno-datos">
                <span><strong>{formatearNumero(t.unidades)}</strong> unidades</span>
                <span><strong>{t.visitas}</strong> visitas</span>
                <span><strong>{t.trabajadores}</strong> trabajadores</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ============ POR TRABAJADOR ============ */}
      <div className="reportes-card">
        <div className="reportes-card-header">
          <FaUsers /> Por trabajador
          <span className="rct-ayuda-tabla">Toca una fila para ver todo lo que retiró</span>
        </div>

        {cargando ? (
          <div className="loading-state">Cargando reporte...</div>
        ) : trabajadores.length === 0 ? (
          <div className="empty-state">Sin entregas registradas con estos filtros.</div>
        ) : (
          <>
            <div className="table-responsive">
              <table className="rct-tabla">
                <thead>
                  <tr>
                    <th>Trabajador</th>
                    <th>Turno</th>
                    <th className="rct-der">Unidades</th>
                    <th className="rct-der">Visitas</th>
                    <th>Lo que más retira</th>
                    <th className="rct-der">Estado</th>
                    <th aria-label="Expandir" />
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((t) => {
                    const abierto = expandido === t.trabajador_id;
                    const principales = t.desglose_por_producto.slice(0, PRODUCTOS_EN_RESUMEN);
                    const restantes = t.desglose_por_producto.length - principales.length;
                    return (
                      <Fragment key={t.trabajador_id}>
                        <tr
                          className={`rct-fila ${t.estado_revision === 'revisar' ? 'rct-fila-revisar' : ''} ${abierto ? 'rct-fila-abierta' : ''}`}
                          onClick={() => setExpandido(abierto ? null : t.trabajador_id)}
                        >
                          <td>
                            <div className="rct-nombre">{t.trabajador_nombre}</div>
                            <div className="rct-sub">{t.cargo}{esAdministrador && ` · ${t.rut}`}</div>
                          </td>
                          <td
                            data-label="Turno"
                            data-resumen={`${formatearNumero(t.total_unidades)} unidades · ${t.num_visitas} visitas`}
                          >
                            <span className={`rct-chip-turno rct-chip-${t.turno_principal}`}>
                              {t.turno_principal === 'noche' ? <FaMoon /> : <FaSun />} {etiquetaTurno(t.turno_principal)}
                            </span>
                          </td>
                          <td className="rct-der rct-num" data-label="Unidades">{formatearNumero(t.total_unidades)}</td>
                          <td className="rct-der rct-num" data-label="Visitas">{t.num_visitas}</td>
                          <td className="rct-productos" data-label="Lo que más retira">
                            {principales.map((p) => `${p.producto_nombre} (${formatearNumero(p.cantidad)})`).join(' · ')}
                            {restantes > 0 && <span className="rct-sub"> +{restantes} más</span>}
                          </td>
                          <td className="rct-der" data-label="Estado">
                            {t.estado_revision === 'revisar' ? (
                              <span
                                className="badge-revisar"
                                title={`Retiró ${formatearNumero(t.total_unidades)}; el promedio de su cargo es ${formatearNumero(t.promedio_cargo)}`}
                              >
                                <FaFlag /> Revisar
                              </span>
                            ) : (
                              <span className="badge-normal">Normal</span>
                            )}
                          </td>
                          <td className="rct-flecha">{abierto ? <FaChevronUp /> : <FaChevronDown />}</td>
                        </tr>

                        {abierto && (
                          <tr className="rct-detalle">
                            <td colSpan={7}>
                              <div className="rct-detalle-cuerpo">
                                <div className="rct-detalle-resumen">
                                  <span><strong>{t.unidades_por_visita}</strong> unidades por visita</span>
                                  <span>Promedio de su cargo: <strong>{formatearNumero(t.promedio_cargo)}</strong> ({t.companeros_en_cargo} personas)</span>
                                  <span><FaSun /> {formatearNumero(t.unidades_por_turno.dia)} · <FaMoon /> {formatearNumero(t.unidades_por_turno.noche)}</span>
                                </div>
                                <ul className="rct-detalle-lista">
                                  {t.desglose_por_producto.map((p) => (
                                    <li key={p.producto_nombre}>
                                      <span>{p.producto_nombre}</span>
                                      <strong className="rct-num">{formatearNumero(p.cantidad)}</strong>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {trabajadores.length > FILAS_INICIALES && (
              <button type="button" className="rct-ver-todos" onClick={() => setVerTodos((v) => !v)}>
                {verTodos ? 'Ver menos' : `Ver los ${trabajadores.length} trabajadores`}
              </button>
            )}
          </>
        )}
      </div>

      {/* ============ HISTORIAL PROPIO ============ */}
      <div className="reportes-card casos-revisar-card">
        <div className="reportes-card-header">
          <FaExclamationTriangle /> Retiró más de lo que acostumbra ({reporte.casos_revisar_historico.length})
        </div>

        <p className="casos-revisar-desc">
          Compara a cada trabajador con su propia historia, no con el resto del equipo. Es informativo:
          solo marca para revisar, nunca bloquea ni acusa.
        </p>

        {reporte.casos_revisar_historico.length === 0 ? (
          <div className="empty-state">Nadie retiró más de lo habitual en este período.</div>
        ) : (
          <ul className="rct-casos">
            {reporte.casos_revisar_historico.map((c) => (
              <li key={`${c.trabajador_id}-${c.inventario_id}`}>
                <div>
                  <div className="rct-nombre">{c.trabajador_nombre}</div>
                  <div className="rct-sub">{c.cargo}</div>
                </div>
                <div className="rct-caso-dato">
                  <strong>{c.producto_nombre}</strong>: {formatearNumero(c.promedio_periodo)} por visita
                  <span className="rct-sub"> (lo habitual: {formatearNumero(c.promedio_historico)})</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default ReporteConsumoTurno;
