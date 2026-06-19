import { useState, useEffect, useRef } from 'react';
import SignatureCanvas from 'react-signature-canvas';
import { FaUser, FaSearch, FaPenFancy, FaHardHat, FaWifi, FaSignal } from 'react-icons/fa';
import api from '../../api';
import { db } from '../../db';
import './Entregas.css';

const Entregas = () => {
    const [entregas, setEntregas] = useState([]);
    const [trabajadores, setTrabajadores] = useState([]);
    const [epps, setEpps] = useState([]);
    const [usuarios, setUsuarios] = useState([]); 
    
    const [error, setError] = useState('');
    const [exito, setExito] = useState('');
    const [isOffline, setIsOffline] = useState(!navigator.onLine);

    const [usuarioSeleccionado, setUsuarioSeleccionado] = useState('');
    const [rutBusqueda, setRutBusqueda] = useState('');
    const [trabajadorSeleccionado, setTrabajadorSeleccionado] = useState(null);
    const [eppsSeleccionados, setEppsSeleccionados] = useState({}); 

    const sigCanvas = useRef({});

    useEffect(() => {
        // Listeners para detectar cambios de red en tiempo real
        const handleOnline = () => {
            setIsOffline(false);
            sincronizarEntregasPendientes();
            cargarDatos();
        };
        const handleOffline = () => setIsOffline(true);

        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

        cargarDatos();

        return () => {
            window.removeEventListener('online', handleOnline);
            window.removeEventListener('offline', handleOffline);
        };
    }, []);

    const cargarDatos = async () => {
        try {
            if (navigator.onLine) {
                const [resEntregas, resTrab, resEpps, resUsuarios] = await Promise.all([
                    api.get('/entregas-epp/').catch(() => ({ data: [] })),
                    api.get('/trabajadores/'),
                    api.get('/epps/'),
                    api.get('/usuarios/').catch(() => ({ data: [] }))
                ]);
                
                setEntregas(resEntregas.data);
                setTrabajadores(resTrab.data);
                setEpps(resEpps.data);
                setUsuarios(resUsuarios.data);

                // Caché en vivo (Actualiza IndexedDB silenciosamente)
                await db.cache_trabajadores.bulkPut(resTrab.data);
                await db.cache_inventario.bulkPut(resEpps.data);
                await db.cache_usuarios.bulkPut(resUsuarios.data);
            } else {
                throw new Error('Modo Offline Forzado');
            }
        } catch (err) {
            // FALLBACK OFFLINE: Consumir de Dexie.js
            setIsOffline(true);
            setError('Sin conexión. Operando con caché local (Modo Terreno).');
            
            const localTrab = await db.cache_trabajadores.toArray();
            const localEpps = await db.cache_inventario.toArray();
            const localUsu = await db.cache_usuarios.toArray();
            
            setTrabajadores(localTrab);
            setEpps(localEpps);
            setUsuarios(localUsu);
        }
    };

    const sincronizarEntregasPendientes = async () => {
        const pendientes = await db.entregas_pendientes.where({ sincronizado: 0 }).toArray();
        if (pendientes.length === 0) return;

        setExito(`Sincronizando ${pendientes.length} entregas locales con el servidor...`);

        for (const entrega of pendientes) {
            try {
                const resEntrega = await api.post('/entregas-epp/', {
                    trabajador: entrega.trabajador_id,
                    usuario: entrega.usuario_id, 
                    observacion: 'Entrega sincronizada (Modo Terreno)', 
                    firma_base64: entrega.firma_base64,
                    estado: 'COMPLETADA'
                });

                const entregaId = resEntrega.data.id;

                for (const eppId of Object.keys(entrega.epps)) {
                    await api.post('/detalles-entrega/', {
                        entrega: entregaId,
                        epp: parseInt(eppId),
                        cantidad: entrega.epps[eppId],
                        talla: 'N/A' 
                    });

                    // Descontar del API
                    const eppData = await db.cache_inventario.get(parseInt(eppId));
                    if (eppData) {
                        const nuevoStock = parseFloat(eppData.stock_actual) - parseFloat(entrega.epps[eppId]);
                        await api.patch(`/epps/${eppId}/`, { stock_actual: nuevoStock });
                    }
                }
                
                // Marcar como sincronizado y eliminar localmente para evitar duplicados
                await db.entregas_pendientes.delete(entrega.id);
            } catch (err) {
                console.error('Error sincronizando registro:', err);
            }
        }
        
        cargarDatos();
        setExito('✅ Sincronización offline completada exitosamente.');
    };

    const handleBuscarRut = () => {
        setError('');
        setExito('');
        const encontrado = trabajadores.find(t => t.rut.toLowerCase().includes(rutBusqueda.toLowerCase()));
        if (encontrado) {
            setTrabajadorSeleccionado(encontrado);
        } else {
            setTrabajadorSeleccionado(null);
            setError('❌ Trabajador no encontrado en la base de datos (ni en caché).');
        }
    };

    const toggleEpp = (id) => {
        setEppsSeleccionados(prev => {
            const newState = { ...prev };
            if (newState[id]) {
                delete newState[id];
            } else {
                newState[id] = 1;
            }
            return newState;
        });
    };

    const updateCantidad = (id, cantidad) => {
        if (cantidad < 1) return;
        setEppsSeleccionados(prev => ({ ...prev, [id]: cantidad }));
    };

    const limpiarFirma = (e) => {
        e.preventDefault();
        sigCanvas.current.clear();
    };

    const handleSubmit = async () => {
        setError('');
        setExito('');

        if (!usuarioSeleccionado) return setError('⚠️ Seleccione el responsable de la entrega.');
        if (!trabajadorSeleccionado) return setError('⚠️ Debe buscar y seleccionar un trabajador.');
        if (Object.keys(eppsSeleccionados).length === 0) return setError('⚠️ Seleccione al menos un EPP a entregar.');
        if (sigCanvas.current.isEmpty()) return setError('⚠️ La firma del trabajador es obligatoria.');

        const firmaBase64 = sigCanvas.current.getCanvas().toDataURL('image/png');

        const payloadLocal = {
            usuario_id: parseInt(usuarioSeleccionado),
            trabajador_id: trabajadorSeleccionado.id,
            epps: eppsSeleccionados,
            firma_base64: firmaBase64,
            fecha: new Date().toISOString(),
            sincronizado: 0
        };

        try {
            if (!isOffline && navigator.onLine) {
                // FLUJO ONLINE
                const resEntrega = await api.post('/entregas-epp/', {
                    trabajador: payloadLocal.trabajador_id,
                    usuario: payloadLocal.usuario_id,
                    observacion: 'Entrega generada desde App', 
                    firma_base64: payloadLocal.firma_base64,
                    estado: 'COMPLETADA'
                });

                const entregaId = resEntrega.data.id;

                for (const eppId of Object.keys(payloadLocal.epps)) {
                    const cantidadEntregada = payloadLocal.epps[eppId];
                    await api.post('/detalles-entrega/', {
                        entrega: entregaId,
                        epp: parseInt(eppId),
                        cantidad: cantidadEntregada,
                        talla: 'N/A' 
                    });

                    // Actualizar API y Caché
                    const eppData = epps.find(e => e.id === parseInt(eppId));
                    if (eppData) {
                        const nuevoStock = parseFloat(eppData.stock_actual) - parseFloat(cantidadEntregada);
                        await api.patch(`/epps/${eppId}/`, { stock_actual: nuevoStock });
                        await db.cache_inventario.update(parseInt(eppId), { stock_actual: nuevoStock });
                    }
                }
                setExito('✅ ¡Entrega confirmada y sincronizada con el servidor!');
            } else {
                // FLUJO OFFLINE: Guardar en Dexie
                await db.entregas_pendientes.add(payloadLocal);
                
                // Descontar stock visualmente en la caché local para prevenir sobre-entregas
                for (const eppId of Object.keys(payloadLocal.epps)) {
                    const eppData = await db.cache_inventario.get(parseInt(eppId));
                    if (eppData) {
                        const nuevoStock = parseFloat(eppData.stock_actual) - parseFloat(payloadLocal.epps[eppId]);
                        await db.cache_inventario.update(parseInt(eppId), { stock_actual: nuevoStock });
                    }
                }
                
                setExito('📡 Guardado Localmente. Se sincronizará automáticamente al recuperar la conexión.');
            }

            // Limpieza de estados
            setTrabajadorSeleccionado(null);
            setRutBusqueda('');
            setEppsSeleccionados({});
            setUsuarioSeleccionado('');
            sigCanvas.current.clear();
            cargarDatos();
            window.scrollTo({ top: 0, behavior: 'smooth' });

        } catch (err) {
            console.error(err);
            if (err.response && err.response.data) {
                setError(`❌ Error de validación: ${JSON.stringify(err.response.data)}`);
            } else {
                // Si la red falla durante la petición, forzamos offline y guardamos localmente
                setIsOffline(true);
                await db.entregas_pendientes.add(payloadLocal);
                setExito('Red inestable. Transacción resguardada localmente.');
                setTrabajadorSeleccionado(null);
                sigCanvas.current.clear();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }
    };

    return (
        <div className="entregas-wrapper">
            <div className="header-status">
                <h1 className="page-title">Entrega de EPP</h1>
                <div className={`network-badge ${isOffline ? 'badge-offline' : 'badge-online'}`}>
                    {isOffline ? <><FaSignal /> Modo Offline</> : <><FaWifi /> Conectado</>}
                </div>
            </div>
            
            {error && <div className="alert alert-error">{error}</div>}
            {exito && <div className="alert alert-success">{exito}</div>}

            {/* PASO 1: RESPONSABLE */}
            <div className="step-card">
                <div className="step-header">
                    <span>1. RESPONSABLE DE ENTREGA</span>
                    <FaHardHat />
                </div>
                <div className="step-body">
                    <select 
                        className="custom-select"
                        value={usuarioSeleccionado} 
                        onChange={(e) => setUsuarioSeleccionado(e.target.value)}
                    >
                        <option value="">-- Seleccione su usuario --</option>
                        {usuarios.map(u => (
                            <option key={u.id} value={u.id}>{u.username} ({u.first_name} {u.last_name})</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* PASO 2: BUSCADOR */}
            <div className="step-card">
                <div className="step-header">
                    <span>2. IDENTIFICACIÓN TRABAJADOR</span>
                    <FaUser />
                </div>
                <div className="step-body">
                    <div className="search-input-wrapper">
                        <span className="search-icon-box"><FaSearch /></span>
                        <input 
                            type="text" 
                            placeholder="Ingrese RUT (Ej: 12.345.678-k)" 
                            value={rutBusqueda}
                            onChange={(e) => setRutBusqueda(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleBuscarRut()}
                        />
                        <button className="btn-buscar-rut" onClick={handleBuscarRut}>BUSCAR</button>
                    </div>
                </div>
            </div>

            {/* PASO 3: FLUJO OCULTO HASTA ENCONTRAR TRABAJADOR */}
            {trabajadorSeleccionado && (
                <>
                    <div className="step-card">
                        <div className="step-header">DATOS DEL TRABAJADOR</div>
                        <div className="step-body">
                            <div className="worker-data-grid">
                                <span className="data-label">Nombre:</span>
                                <span className="data-value">{trabajadorSeleccionado.nombres} {trabajadorSeleccionado.apellido_paterno}</span>
                                
                                <span className="data-label">RUT:</span>
                                <span className="data-value">{trabajadorSeleccionado.rut}</span>
                                
                                <span className="data-label">Cargo:</span>
                                <span className="data-value">{trabajadorSeleccionado.cargo}</span>
                            </div>
                        </div>
                    </div>

                    <div className="step-card">
                        <div className="step-header">SELECCIÓN DE EPP</div>
                        <div className="step-body">
                            <div className="epp-list">
                                {epps.map(epp => {
                                    const isSelected = !!eppsSeleccionados[epp.id];
                                    return (
                                        <div key={epp.id} className={`epp-item ${isSelected ? 'selected' : ''}`}>
                                            <div className="epp-item-left" onClick={() => toggleEpp(epp.id)}>
                                                <input 
                                                    type="checkbox" 
                                                    className="epp-checkbox" 
                                                    checked={isSelected}
                                                    readOnly
                                                />
                                                <span>{epp.nombre} <small className="epp-stock-info">(Stock: {epp.stock_actual})</small></span>
                                            </div>
                                            {isSelected && (
                                                <input 
                                                    type="number" 
                                                    className="epp-qty-input"
                                                    value={eppsSeleccionados[epp.id]}
                                                    onChange={(e) => updateCantidad(epp.id, e.target.value)}
                                                    min="1"
                                                    max={epp.stock_actual}
                                                />
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    <div className="step-card">
                        <div className="step-header">
                            <span>FIRMA DIGITAL DEL TRABAJADOR</span>
                            <FaPenFancy />
                        </div>
                        <div className="step-body step-body-padded">
                            <div className="signature-container">
                                <div className="signature-instructions">
                                    Firme dentro del cuadro con su dedo o mouse para consentir
                                </div>
                                <div className="signature-pad-wrapper">
                                    <SignatureCanvas 
                                        ref={sigCanvas} 
                                        penColor="#001529"
                                        canvasProps={{ className: 'sigCanvas' }} 
                                    />
                                    <div className="signature-line">
                                        <span>Firme Aquí</span>
                                    </div>
                                </div>
                                <button className="btn-clear-sig" onClick={limpiarFirma}>Borrar firma</button>
                            </div>
                        </div>
                    </div>

                    <button className="btn-confirmar-main" onClick={handleSubmit}>
                        CONFIRMAR ENTREGA
                    </button>
                </>
            )}

            <h3 className="history-title">Historial Reciente {isOffline && '(Local)'}</h3>
            <div className="history-table-wrapper">
                <table className="history-table">
                    <thead>
                        <tr>
                            <th>Nº Doc</th>
                            <th>Trabajador</th>
                            <th>Fecha</th>
                            <th>Firma</th>
                        </tr>
                    </thead>
                    <tbody>
                        {entregas.length === 0 ? (
                            <tr><td colSpan="4" className="text-center-padded">No hay entregas registradas.</td></tr>
                        ) : (
                            [...entregas].reverse().slice(0, 10).map((entrega) => (
                                <tr key={entrega.id}>
                                    <td><strong>#{entrega.id}</strong></td>
                                    <td className="fw-bold">{entrega.nombre_trabajador || entrega.trabajador_id}</td>
                                    <td>{new Date(entrega.fecha_entrega || entrega.fecha).toLocaleString()}</td>
                                    <td>
                                        {entrega.firma_base64 ? (
                                            <img src={entrega.firma_base64} alt="Firma" className="history-signature-img" />
                                        ) : 'N/A'}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            
        </div>
    );
};

export default Entregas;