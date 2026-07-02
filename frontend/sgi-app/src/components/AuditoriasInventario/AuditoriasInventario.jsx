import { useEffect, useState } from 'react';
import { FaSearch, FaFileExcel, FaEye, FaClipboardCheck } from 'react-icons/fa';
import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';
import api from '../../api';
import './AuditoriasInventario.css';

const AuditoriasInventario = () => {
  const [auditorias, setAuditorias] = useState([]);
  const [detalle, setDetalle] = useState(null);
  const [busqueda, setBusqueda] = useState('');
  const [estado, setEstado] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    cargarAuditorias();
  }, []);

  const cargarAuditorias = async () => {
    try {
      const res = await api.get('/auditorias-inventario/');
      setAuditorias(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Error al cargar auditorías.');
    }
  };

  const verDetalle = async (id) => {
    try {
      const res = await api.get(`/auditorias-inventario/${id}/detalle/`);
      setDetalle(res.data);
    } catch {
      setError('No se pudo cargar el detalle.');
    }
  };

  const auditoriasFiltradas = auditorias.filter((a) => {
    const texto = busqueda.toLowerCase();

    const coincideTexto =
      String(a.id).includes(texto) ||
      String(a.bodega_nombre || '').toLowerCase().includes(texto) ||
      String(a.usuario_nombre || '').toLowerCase().includes(texto);

    const coincideEstado = estado ? a.estado === estado : true;

    return coincideTexto && coincideEstado;
  });

  const exportarExcel = async () => {
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Auditorías');

    sheet.columns = [
      { header: 'ID', key: 'id', width: 12 },
      { header: 'Bodega', key: 'bodega', width: 28 },
      { header: 'Usuario', key: 'usuario', width: 24 },
      { header: 'Inicio', key: 'inicio', width: 24 },
      { header: 'Cierre', key: 'cierre', width: 24 },
      { header: 'Estado', key: 'estado', width: 18 },
      { header: 'Observación', key: 'observacion', width: 45 },
    ];

    sheet.getRow(1).eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEA580C' } };
      cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      cell.alignment = { horizontal: 'center' };
    });

    auditoriasFiltradas.forEach((a) => {
      sheet.addRow({
        id: a.id,
        bodega: a.bodega_nombre || 'N/A',
        usuario: a.usuario_nombre || 'N/A',
        inicio: a.fecha_inicio ? new Date(a.fecha_inicio).toLocaleString() : 'N/A',
        cierre: a.fecha_cierre ? new Date(a.fecha_cierre).toLocaleString() : 'N/A',
        estado: a.estado,
        observacion: a.observacion || '',
      });
    });

    const buffer = await workbook.xlsx.writeBuffer();
    saveAs(
      new Blob([buffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }),
      `Auditorias_Inventario_${Date.now()}.xlsx`
    );
  };

  return (
    <div className="auditorias-wrapper">
      <div className="auditorias-header">
        <div>
          <h1><FaClipboardCheck /> Auditorías de Inventario</h1>
          <p>Historial y revisión de conteos cíclicos realizados.</p>
        </div>

        <button className="btn-excel" onClick={exportarExcel}>
          <FaFileExcel /> Exportar Excel
        </button>
      </div>

      {error && <div className="auditoria-error">{error}</div>}

      <div className="auditoria-filtros">
        <div className="filter-box">
          <FaSearch />
          <input
            placeholder="Buscar por ID, bodega o usuario..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        </div>

        <select value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="">Todos los estados</option>
          <option value="ABIERTA">Abierta</option>
          <option value="CERRADA">Cerrada</option>
          <option value="ANULADA">Anulada</option>
        </select>
      </div>

      <div className="auditorias-grid">
        {auditoriasFiltradas.map((a) => (
          <div key={a.id} className="auditoria-card">
            <div className="auditoria-card-top">
              <strong>Auditoría #{a.id}</strong>
              <span className={`estado estado-${a.estado.toLowerCase()}`}>
                {a.estado}
              </span>
            </div>

            <p><b>Bodega:</b> {a.bodega_nombre || 'N/A'}</p>
            <p><b>Usuario:</b> {a.usuario_nombre || 'N/A'}</p>
            <p><b>Inicio:</b> {a.fecha_inicio ? new Date(a.fecha_inicio).toLocaleString() : 'N/A'}</p>
            <p><b>Cierre:</b> {a.fecha_cierre ? new Date(a.fecha_cierre).toLocaleString() : 'Pendiente'}</p>

            <button className="btn-detalle" onClick={() => verDetalle(a.id)}>
              <FaEye /> Ver detalle
            </button>
          </div>
        ))}
      </div>

      {detalle && (
        <div className="detalle-panel">
          <div className="detalle-header">
            <h2>Detalle Auditoría #{detalle.auditoria}</h2>
            <button onClick={() => setDetalle(null)}>Cerrar</button>
          </div>

          <table className="detalle-table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Producto</th>
                <th>Sistema</th>
                <th>Físico</th>
                <th>Diferencia</th>
                <th>Observación</th>
              </tr>
            </thead>

            <tbody>
              {detalle.detalle.length === 0 ? (
                <tr>
                  <td colSpan="6" className="empty-row">Sin diferencias registradas.</td>
                </tr>
              ) : (
                detalle.detalle.map((d, index) => (
                  <tr key={index}>
                    <td>{d.codigo}</td>
                    <td>{d.producto}</td>
                    <td>{d.stock_sistema}</td>
                    <td>{d.stock_fisico}</td>
                    <td className={Number(d.diferencia) === 0 ? 'ok' : 'danger'}>
                      {d.diferencia}
                    </td>
                    <td>{d.observacion || 'N/A'}</td>
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

export default AuditoriasInventario;