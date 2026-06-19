import { useState, useEffect } from 'react';
import { FaFilePdf, FaFileExcel, FaSearch, FaFilter, FaCalendarAlt } from 'react-icons/fa';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import ExcelJS from 'exceljs'; // Nuevo motor premium para Excel
import { saveAs } from 'file-saver'; // Descargador de archivos
import api from '../../api';
import { db } from '../../db';
import './Reportes.css';

const Reportes = () => {
    const [entregas, setEntregas] = useState([]);
    const [trabajadores, setTrabajadores] = useState([]);
    const [cargando, setCargando] = useState(true);
    const [error, setError] = useState('');
    const [isOffline, setIsOffline] = useState(!navigator.onLine);

    // Filtros
    const [filtroMes, setFiltroMes] = useState('');
    const [filtroRut, setFiltroRut] = useState('');

    useEffect(() => {
        const handleOnline = () => setIsOffline(false);
        const handleOffline = () => setIsOffline(true);

        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

        cargarDatosParaReportes();

        return () => {
            window.removeEventListener('online', handleOnline);
            window.removeEventListener('offline', handleOffline);
        };
    }, []);

    const cargarDatosParaReportes = async () => {
        setCargando(true);
        setError('');
        try {
            if (navigator.onLine) {
                const [resEntregas, resTrabajadores] = await Promise.all([
                    api.get('/entregas-epp/'),
                    api.get('/trabajadores/')
                ]);
                setEntregas(resEntregas.data);
                setTrabajadores(resTrabajadores.data);
            } else {
                throw new Error("Forzando lectura local por falta de red");
            }
        } catch (err) {
            setIsOffline(true);
            try {
                // MODO OFFLINE: Consumimos de Dexie
                const entregasLocales = await db.entregas_pendientes.toArray();
                const trabajadoresLocales = await db.cache_trabajadores.toArray();
                
                const entregasAdaptadas = entregasLocales.map(e => ({
                    id: `Local-${e.id}`,
                    nombre_trabajador: `RUT/ID: ${e.trabajador_id}`,
                    fecha_entrega: e.fecha,
                    estado: 'PENDIENTE SINC.'
                }));

                setEntregas(entregasAdaptadas);
                setTrabajadores(trabajadoresLocales);
            } catch (dexieErr) {
                setError('No hay datos locales disponibles para generar el reporte.');
            }
        } finally {
            setCargando(false);
        }
    };

    const entregasFiltradas = entregas.filter(entrega => {
        let coincideRut = true;
        let coincideMes = true;

        if (filtroRut) {
            coincideRut = entrega.nombre_trabajador?.toLowerCase().includes(filtroRut.toLowerCase());
        }
        
        if (filtroMes && entrega.fecha_entrega) {
            const fecha = new Date(entrega.fecha_entrega);
            const mesEntrega = `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}`;
            coincideMes = mesEntrega === filtroMes;
        }

        return coincideRut && coincideMes;
    });

    // --- MOTOR GENERADOR DE PDF ---
    const generarPDF = () => {
        if (entregasFiltradas.length === 0) {
            alert("⚠️ No hay datos para exportar con los filtros actuales.");
            return;
        }

        try {
            const doc = new jsPDF();
            
            doc.setFillColor(0, 21, 41); 
            doc.rect(0, 0, 210, 25, 'F');
            doc.setTextColor(255, 255, 255);
            doc.setFontSize(16);
            doc.setFont("helvetica", "bold");
            doc.text("NEXOFAENA SGI", 14, 12);
            doc.setFontSize(10);
            doc.setFont("helvetica", "normal");
            doc.text("Reporte Oficial de Entregas de EPP", 14, 18);
            
            const fechaReporte = new Date().toLocaleString();
            doc.setFontSize(8);
            doc.text(`Generado: ${fechaReporte} ${isOffline ? '(Modo Terreno)' : ''}`, 130, 18);

            const tableColumn = ["Nº Transacción", "Trabajador / Identificación", "Fecha de Entrega", "Estado"];
            const tableRows = [];

            entregasFiltradas.forEach(entrega => {
                const fechaFormateada = entrega.fecha_entrega 
                    ? new Date(entrega.fecha_entrega).toLocaleDateString() 
                    : 'N/A';
                    
                const entregaData = [
                    entrega.id,
                    entrega.nombre_trabajador || "No registrado",
                    fechaFormateada,
                    entrega.estado || "COMPLETADA"
                ];
                tableRows.push(entregaData);
            });

            autoTable(doc, {
                head: [tableColumn],
                body: tableRows,
                startY: 35,
                theme: 'grid',
                headStyles: { 
                    fillColor: [234, 88, 12], 
                    textColor: [255, 255, 255],
                    fontStyle: 'bold'
                },
                alternateRowStyles: { 
                    fillColor: [245, 247, 250] 
                },
                styles: { fontSize: 9, cellPadding: 4 }
            });

            doc.save(`Reporte_Entregas_${new Date().getTime()}.pdf`);
            
        } catch (error) {
            console.error("Error crítico al generar el PDF:", error);
            alert("Hubo un error al compilar el PDF. Revisa la consola para más detalles.");
        }
    };

    // --- MOTOR GENERADOR DE EXCEL PREMIUM ---
    const generarExcel = async () => {
        if (entregasFiltradas.length === 0) {
            alert("⚠️ No hay datos para exportar con los filtros actuales.");
            return;
        }

        try {
            const workbook = new ExcelJS.Workbook();
            workbook.creator = 'NexoFaena SGI';
            workbook.created = new Date();

            // Quitar las líneas de cuadrícula grises feas de Excel por defecto
            const worksheet = workbook.addWorksheet('Historial de Entregas', {
                views: [{ showGridLines: false }] 
            });

            // 1. Configuración de Columnas con anchos adaptativos
            worksheet.columns = [
                { header: 'Nº Transacción', key: 'id', width: 20 },
                { header: 'Trabajador / Identificación', key: 'trabajador', width: 45 },
                { header: 'Fecha de Entrega', key: 'fecha', width: 25 },
                { header: 'Estado', key: 'estado', width: 22 }
            ];

            // 2. Dar estilo Premium a la Cabecera (Header)
            const headerRow = worksheet.getRow(1);
            headerRow.height = 30; // Altura más espaciosa
            headerRow.eachCell((cell) => {
                // Fondo Naranja Corporativo
                cell.fill = {
                    type: 'pattern',
                    pattern: 'solid',
                    fgColor: { argb: 'FFEA580C' } 
                };
                // Letra Blanca y Negrita
                cell.font = {
                    color: { argb: 'FFFFFFFF' },
                    bold: true,
                    size: 11,
                    name: 'Arial'
                };
                // Alineación centrada
                cell.alignment = { vertical: 'middle', horizontal: 'center' };
                // Bordes sutiles
                cell.border = {
                    top: { style: 'thin', color: { argb: 'FFCCCCCC' } },
                    bottom: { style: 'medium', color: { argb: 'FF001529' } } // Borde inferior Dark Premium
                };
            });

            // 3. Poblar y Estilizar los Datos (Efecto Cebra)
            entregasFiltradas.forEach((entrega, index) => {
                const row = worksheet.addRow({
                    id: entrega.id,
                    trabajador: entrega.nombre_trabajador || "No registrado",
                    fecha: entrega.fecha_entrega ? new Date(entrega.fecha_entrega).toLocaleString() : 'N/A',
                    estado: entrega.estado || "COMPLETADA"
                });

                row.height = 20; // Filas de datos más cómodas de leer

                row.eachCell((cell, colNumber) => {
                    // Alineación
                    cell.alignment = { 
                        vertical: 'middle', 
                        horizontal: colNumber === 2 ? 'left' : 'center' // Nombre a la izquierda, resto centrado
                    };
                    
                    // Bordes inferiores sutiles para cada fila
                    cell.border = {
                        bottom: { style: 'thin', color: { argb: 'FFEEEEEE' } },
                        left: { style: 'thin', color: { argb: 'FFEEEEEE' } },
                        right: { style: 'thin', color: { argb: 'FFEEEEEE' } }
                    };

                    // Efecto Cebra: Filas alternas con un fondo gris clarito
                    if (index % 2 === 0) {
                        cell.fill = {
                            type: 'pattern',
                            pattern: 'solid',
                            fgColor: { argb: 'FFF9FAFB' } // Gris muy suave
                        };
                    }
                });
            });

            // 4. Compilar y Descargar (Compatible con Modo Offline)
            const buffer = await workbook.xlsx.writeBuffer();
            const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
            saveAs(blob, `NexoFaena_Reporte_EPP_${new Date().getTime()}.xlsx`);

        } catch (error) {
            console.error("Error crítico al generar el Excel Premium:", error);
            alert("Hubo un error al compilar el archivo Excel. Revisa la consola para más detalles.");
        }
    };

    return (
        <div className="reportes-wrapper">
            <div className="reportes-header">
                <div>
                    <h1 className="page-title">Módulo de Reportes</h1>
                    <p className="page-subtitle">Exportación de datos de bodega y entregas</p>
                </div>
                <div className={`status-badge ${isOffline ? 'offline-badge' : 'online-badge'}`}>
                    {isOffline ? 'Operando Offline' : 'Conectado'}
                </div>
            </div>

            <div className="reportes-toolbar">
                <div className="filters-container">
                    <div className="filter-group">
                        <FaSearch className="filter-icon" />
                        <input 
                            type="text" 
                            className="filter-input" 
                            placeholder="Filtrar por RUT o Nombre..."
                            value={filtroRut}
                            onChange={(e) => setFiltroRut(e.target.value)}
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
                </div>

                <div className="export-buttons-group">
                    <button className="btn-export-pdf" onClick={generarPDF} disabled={cargando}>
                        <FaFilePdf /> EXPORTAR A PDF
                    </button>
                    <button className="btn-export-excel" onClick={generarExcel} disabled={cargando}>
                        <FaFileExcel /> EXPORTAR A EXCEL
                    </button>
                </div>
            </div>

            <div className="reportes-card">
                <div className="reportes-card-header">
                    <FaFilter /> Vista Previa de Datos ({entregasFiltradas.length} registros)
                </div>
                
                {cargando ? (
                    <div className="loading-state">Cargando registros...</div>
                ) : error ? (
                    <div className="error-state">{error}</div>
                ) : (
                    <div className="table-responsive">
                        <table className="reportes-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Trabajador</th>
                                    <th>Fecha</th>
                                    <th>Estado</th>
                                </tr>
                            </thead>
                            <tbody>
                                {entregasFiltradas.length > 0 ? (
                                    entregasFiltradas.map((e, index) => (
                                        <tr key={index}>
                                            <td><strong>#{e.id}</strong></td>
                                            <td>{e.nombre_trabajador}</td>
                                            <td>{e.fecha_entrega ? new Date(e.fecha_entrega).toLocaleDateString() : 'N/A'}</td>
                                            <td>
                                                <span className={`estado-etiqueta ${e.estado === 'COMPLETADA' ? 'estado-ok' : 'estado-pendiente'}`}>
                                                    {e.estado || 'COMPLETADA'}
                                                </span>
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan="4" className="empty-state">No se encontraron entregas con estos filtros.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Reportes;