import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import SignatureCanvas from "react-signature-canvas";
import {
  FaCamera, FaTimes, FaWifi, FaSignal, FaCheckCircle,
  FaExclamationTriangle, FaShieldAlt, FaUndo, FaLockOpen,
} from "react-icons/fa";
import api from "../../api";
import { db } from "../../db";
import "./ConteoCiclico.css";

const UMBRAL_DESCUADRE_PORCENTAJE = 0.2;
const AUDITORIA_STORAGE_KEY = "conteo_auditoria_activa";

// Misma regla que el backend (AuditoriaInventarioService._es_descuadre_critico):
// solo decide si se muestra el panel de firma, el backend vuelve a validarlo.
const esDescuadreCritico = (producto) => {
  const diferencia = Number(producto.diferencia || 0);
  if (diferencia >= 0) return false;
  if (producto.es_activo_critico) return true;

  const stockSistema = Number(producto.stock_actual || 0);
  if (stockSistema > 0) {
    return Math.abs(diferencia) / stockSistema > UMBRAL_DESCUADRE_PORCENTAJE;
  }
  return false;
};

const ConteoCiclico = () => {
  const [bodegas, setBodegas] = useState([]);
  const [bodega, setBodega] = useState("");
  const [productos, setProductos] = useState([]);
  const [auditoria, setAuditoria] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [pendientesSync, setPendientesSync] = useState(0);
  const [auditoriasAbiertasBodega, setAuditoriasAbiertasBodega] = useState([]);

  const [scannerAbierto, setScannerAbierto] = useState(false);
  const [scannerError, setScannerError] = useState("");
  const [filaResaltada, setFilaResaltada] = useState(null);
  const html5QrRef = useRef(null);
  const filaRefs = useRef({});
  const inputRefs = useRef({});

  const [mostrarFirma, setMostrarFirma] = useState(false);
  const [errorFirma, setErrorFirma] = useState("");
  const sigCanvas = useRef(null);

  useEffect(() => {
    const handleOnline = () => {
      setIsOffline(false);
      sincronizarConteosPendientes();
    };
    const handleOffline = () => setIsOffline(true);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    cargarBodegas();
    restaurarSesion();
    actualizarContadorPendientes();

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      detenerEscaner();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (bodega) {
      cargarProductos();
      verificarAuditoriasAbiertas(bodega);
    } else {
      setProductos([]);
      setAuditoriasAbiertasBodega([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bodega]);

  useEffect(() => {
    if (!scannerAbierto) return undefined;

    const instancia = new Html5Qrcode("qr-reader-conteo");
    html5QrRef.current = instancia;

    instancia
      .start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        (decodedText) => onEscaneoExitoso(decodedText),
        () => {}
      )
      .catch(() => {
        setScannerError("No se pudo acceder a la cámara. Verifica los permisos del navegador.");
      });

    return () => {
      detenerEscaner();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scannerAbierto]);

  const restaurarSesion = () => {
    const guardado = localStorage.getItem(AUDITORIA_STORAGE_KEY);
    if (!guardado) return;

    try {
      const datos = JSON.parse(guardado);
      if (datos?.id && datos?.bodega) {
        setAuditoria(datos);
        setBodega(String(datos.bodega));
        setMensaje("Se restauró una auditoría en curso guardada en este dispositivo.");
      }
    } catch {
      localStorage.removeItem(AUDITORIA_STORAGE_KEY);
    }
  };

  const guardarSesion = (datosAuditoria) => {
    localStorage.setItem(AUDITORIA_STORAGE_KEY, JSON.stringify(datosAuditoria));
  };

  const limpiarSesion = () => {
    localStorage.removeItem(AUDITORIA_STORAGE_KEY);
  };

  const actualizarContadorPendientes = async () => {
    const total = await db.conteos_pendientes.count();
    setPendientesSync(total);
  };

  const cargarBodegas = async () => {
    if (!navigator.onLine) return;

    try {
      const res = await api.get("/bodegas/");
      setBodegas(res.data);
    } catch {
      setError("No se pudieron cargar las bodegas.");
    }
  };

  const verificarAuditoriasAbiertas = async (bodegaId) => {
    if (!bodegaId || !navigator.onLine) {
      setAuditoriasAbiertasBodega([]);
      return;
    }

    try {
      const res = await api.get(`/auditorias-inventario/?bodega=${bodegaId}&estado=ABIERTA`);
      setAuditoriasAbiertasBodega(Array.isArray(res.data) ? res.data : []);
    } catch {
      setAuditoriasAbiertasBodega([]);
    }
  };

  const reanudarAuditoria = async (a) => {
    setAuditoria(a);
    guardarSesion(a);
    setMensaje(`Retomando auditoría #${a.id} (ya estaba abierta en esta bodega).`);
    setError("");
    await cargarProductos(a);
  };

  const anularAuditoriaAbierta = async (id) => {
    if (!window.confirm(
      `¿Anular la auditoría #${id}? Esta acción no se puede deshacer y descarta cualquier conteo registrado en ella.`
    )) return;

    try {
      await api.post(`/auditorias-inventario/${id}/anular/`);

      // Los conteos locales que aún no habían sincronizado quedan huérfanos:
      // una auditoría anulada nunca vuelve a aceptar registrar_conteo, así que
      // reintentar sincronizarlos solo produciría 400 eternos.
      await db.conteos_pendientes.where({ auditoria_id: id }).delete();
      await actualizarContadorPendientes();

      setMensaje(`Auditoría #${id} anulada. Ya puedes crear una nueva auditoría en esta bodega.`);
      setError("");

      if (auditoria?.id === id) {
        setAuditoria(null);
        limpiarSesion();
      }

      await verificarAuditoriasAbiertas(bodega);
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo anular la auditoría.");
    }
  };

  const cargarProductos = async (auditoriaActual = auditoria) => {
    let lista = [];

    try {
      if (!navigator.onLine) throw new Error("OFFLINE");

      const res = await api.get(`/inventario/?bodega=${bodega}`);
      lista = res.data;
      await db.cache_inventario.bulkPut(lista);
      setIsOffline(false);
      setError("");
    } catch (err) {
      setIsOffline(true);

      const cache = await db.cache_inventario.toArray();
      lista = cache.filter((p) => String(p.bodega) === String(bodega));

      if (lista.length === 0) {
        setError("No hay productos en caché para esta bodega. Conéctate al menos una vez antes de auditar sin señal.");
      } else {
        setError("");
      }
    }

    let productosBase = lista.map((p) => ({
      ...p,
      stock_fisico: p.stock_actual,
      diferencia: 0,
    }));

    if (auditoriaActual?.id) {
      // 1. Conteos ya sincronizados en el servidor (ej. al reanudar una
      // auditoría abierta que otra persona/dispositivo ya avanzó).
      const detallesServidor = auditoriaActual.detalles || [];

      productosBase = productosBase.map((p) => {
        const detalle = detallesServidor.find((d) => d.inventario === p.id);
        if (!detalle) return p;

        return {
          ...p,
          stock_fisico: detalle.stock_fisico,
          diferencia: Number(detalle.diferencia),
        };
      });

      // 2. Conteos locales aún no sincronizados: más recientes, pisan lo anterior.
      const pendientes = await db.conteos_pendientes
        .where({ auditoria_id: auditoriaActual.id })
        .toArray();

      productosBase = productosBase.map((p) => {
        const pendiente = pendientes.find((c) => c.inventario_id === p.id);
        if (!pendiente) return p;

        return {
          ...p,
          stock_fisico: pendiente.stock_fisico,
          diferencia: Number(pendiente.stock_fisico) - Number(p.stock_actual),
        };
      });
    }

    setProductos(productosBase);
  };

  const crearAuditoria = async () => {
    if (!bodega) {
      setError("Primero debe seleccionar una bodega.");
      return;
    }

    if (!navigator.onLine) {
      setError("Debe tener conexión para abrir una nueva auditoría.");
      return;
    }

    try {
      const res = await api.post("/auditorias-inventario/", {
        bodega,
        observacion: "Conteo cíclico",
      });

      setAuditoria(res.data.data);
      guardarSesion(res.data.data);
      setMensaje("Auditoría creada correctamente. Ahora ingrese el conteo físico (funciona sin conexión).");
      setError("");
      await cargarProductos(res.data.data);
      await verificarAuditoriasAbiertas(bodega);
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo crear la auditoría.");
    }
  };

  const actualizarConteo = (index, valor) => {
    const copia = [...productos];

    copia[index].stock_fisico = valor;
    copia[index].diferencia = Number(valor || 0) - Number(copia[index].stock_actual || 0);

    setProductos(copia);
  };

  const guardarConteoLocal = async (auditoriaId, productoId, stockFisico) => {
    const existente = await db.conteos_pendientes
      .where({ auditoria_id: auditoriaId, inventario_id: productoId })
      .first();

    if (existente) {
      await db.conteos_pendientes.update(existente.id, { stock_fisico: stockFisico, sincronizado: 0 });
    } else {
      await db.conteos_pendientes.add({
        auditoria_id: auditoriaId,
        inventario_id: productoId,
        stock_fisico: stockFisico,
        sincronizado: 0,
      });
    }
  };

  const guardarConteo = async () => {
    if (!auditoria) {
      setError("Primero debe crear una auditoría.");
      return;
    }

    if (auditoria.estado !== "ABIERTA") {
      setError("Solo se puede guardar conteo en una auditoría abierta.");
      return;
    }

    try {
      for (const producto of productos) {
        await guardarConteoLocal(auditoria.id, producto.id, producto.stock_fisico);
      }

      await actualizarContadorPendientes();
      setError("");

      if (navigator.onLine) {
        await sincronizarConteosPendientes();
        setMensaje("Conteo guardado y sincronizado correctamente. Ahora puede cerrar la auditoría.");
      } else {
        setMensaje("📡 Conteo guardado en este dispositivo. Se sincronizará automáticamente al recuperar señal.");
      }
    } catch (err) {
      console.error(err);
      setError("No se pudo guardar el conteo localmente.");
    }
  };

  const sincronizarConteosPendientes = async () => {
    const pendientes = await db.conteos_pendientes.toArray();
    if (pendientes.length === 0) return { sincronizados: 0, errores: [] };

    let sincronizados = 0;
    const errores = [];

    for (const item of pendientes) {
      try {
        const res = await api.post(`/auditorias-inventario/${item.auditoria_id}/registrar_conteo/`, {
          inventario: item.inventario_id,
          stock_fisico: item.stock_fisico,
        });

        // Solo se da por sincronizado el conteo si Django confirma con 200/201.
        // Cualquier otra cosa (incluidos errores atrapados abajo) lo deja en la cola.
        if (res.status === 200 || res.status === 201) {
          await db.conteos_pendientes.delete(item.id);
          sincronizados += 1;
        } else {
          const msg = `Conteo pendiente #${item.id} (producto ${item.inventario_id}): respuesta inesperada del servidor (status ${res.status}).`;
          console.error(msg, res.data);
          errores.push(msg);
        }
      } catch (err) {
        const status = err.response?.status;
        const detalle = err.response?.data?.detail || err.response?.data || err.message || "Error desconocido";

        console.error(
          `Error sincronizando conteo pendiente #${item.id} (auditoría ${item.auditoria_id}, producto ${item.inventario_id}):`,
          { status, detalle, error: err }
        );

        // Un 400 es un rechazo definitivo del servidor (dato inválido: producto
        // que ya no pertenece a la bodega, auditoría cerrada, etc.). Reintentar
        // con el mismo payload jamás va a funcionar, así que si lo dejamos en la
        // cola bloquea "Cerrar Auditoría" para siempre. Se descarta y se avisa.
        // Errores de red o 401/403/5xx sí quedan en cola para reintentar.
        if (status === 400) {
          await db.conteos_pendientes.delete(item.id);
          errores.push(
            `Producto ${item.inventario_id}: descartado (rechazo definitivo del servidor) — ${
              typeof detalle === "string" ? detalle : JSON.stringify(detalle)
            }`
          );
        } else {
          errores.push(
            `Producto ${item.inventario_id}: ${status ? `[HTTP ${status}] ` : "[sin respuesta del servidor] "}${
              typeof detalle === "string" ? detalle : JSON.stringify(detalle)
            }`
          );
        }
      }
    }

    await actualizarContadorPendientes();

    if (sincronizados > 0) {
      setMensaje(`✅ ${sincronizados} conteo(s) sincronizado(s) con el servidor.`);
      if (bodega) cargarProductos();
    }

    if (errores.length > 0) {
      setError(
        `No se pudieron sincronizar ${errores.length} conteo(s). ${errores[0]}` +
          (errores.length > 1 ? ` (y ${errores.length - 1} más, revisa la consola)` : "")
      );
    }

    return { sincronizados, errores };
  };

  const forzarSincronizacion = async () => {
    setMensaje("");
    setError("");

    const { sincronizados, errores } = await sincronizarConteosPendientes();

    if (sincronizados === 0 && errores.length === 0) {
      setMensaje("No hay conteos pendientes por sincronizar.");
    }
  };

  const cerrarAuditoria = async () => {
    if (!auditoria) {
      setError("Primero debe crear una auditoría.");
      return;
    }

    if (auditoria.estado !== "ABIERTA") {
      setError("La auditoría ya fue cerrada o anulada.");
      return;
    }

    if (!navigator.onLine) {
      setError("Debe tener conexión para cerrar la auditoría.");
      return;
    }

    const pendientesAuditoria = await db.conteos_pendientes
      .where({ auditoria_id: auditoria.id })
      .count();

    if (pendientesAuditoria > 0) {
      const { errores } = await sincronizarConteosPendientes();

      const siguenPendientes = await db.conteos_pendientes
        .where({ auditoria_id: auditoria.id })
        .count();

      if (siguenPendientes > 0) {
        if (errores.length === 0) {
          setError(`Aún hay ${siguenPendientes} conteo(s) sin sincronizar. Intenta nuevamente en unos segundos.`);
        }
        // Si hubo errores, sincronizarConteosPendientes ya dejó el motivo exacto en pantalla.
        return;
      }
    }

    try {
      const res = await api.post(`/auditorias-inventario/${auditoria.id}/cerrar/`);
      setAuditoria(res.data.data);
      guardarSesion(res.data.data);
      setMensaje("Auditoría cerrada correctamente. Ahora puede ajustar stock.");
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo cerrar la auditoría.");
    }
  };

  const otrasAuditoriasAbiertas = auditoriasAbiertasBodega.filter((a) => a.id !== auditoria?.id);
  const itemsCriticos = productos.filter(esDescuadreCritico);

  const solicitarAjusteStock = () => {
    if (!auditoria) {
      setError("Primero debe crear una auditoría.");
      return;
    }

    if (auditoria.estado !== "CERRADA") {
      setError("Debe cerrar la auditoría antes de ajustar stock.");
      return;
    }

    if (itemsCriticos.length > 0) {
      setErrorFirma("");
      setMostrarFirma(true);
      return;
    }

    ejecutarAjusteStock(null);
  };

  const confirmarFirmaYAjustar = () => {
    if (!sigCanvas.current || sigCanvas.current.isEmpty()) {
      setErrorFirma("La firma del supervisor es obligatoria para continuar.");
      return;
    }

    const firma = sigCanvas.current.getCanvas().toDataURL("image/png");
    setMostrarFirma(false);
    ejecutarAjusteStock(firma);
  };

  const ejecutarAjusteStock = async (firma) => {
    try {
      const res = await api.post(`/auditorias-inventario/${auditoria.id}/ajustar_stock/`, {
        firma_autorizacion: firma,
      });

      // Importante: reflejar el nuevo estado ("AJUSTADA") en el estado local.
      // Si se deja "auditoria" con estado CERRADA, el botón de más abajo
      // sigue habilitado y permite aplicar el mismo ajuste dos veces.
      setAuditoria(res.data.data);
      setMensaje("Stock actualizado correctamente según conteo físico.");
      setError("");
      limpiarSesion();
      cargarProductos();
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo ajustar el stock.");
    }
  };

  // ---- Escáner de código de barras / QR ----
  const abrirEscaner = () => {
    setScannerError("");
    setScannerAbierto(true);
  };

  const detenerEscaner = () => {
    const instancia = html5QrRef.current;
    html5QrRef.current = null;

    if (instancia) {
      instancia.stop().then(() => instancia.clear()).catch(() => {});
    }
  };

  const cerrarEscaner = () => {
    detenerEscaner();
    setScannerAbierto(false);
  };

  const onEscaneoExitoso = (codigoEscaneado) => {
    const texto = codigoEscaneado.trim().toLowerCase();
    const producto = productos.find((p) => p.codigo?.toLowerCase() === texto);

    if (!producto) {
      setScannerError(`Código "${codigoEscaneado}" no encontrado en esta bodega.`);
      return;
    }

    cerrarEscaner();
    setMensaje(`📷 Producto encontrado: ${producto.nombre}`);
    setFilaResaltada(producto.id);

    setTimeout(() => {
      filaRefs.current[producto.id]?.scrollIntoView({ behavior: "smooth", block: "center" });
      inputRefs.current[producto.id]?.focus();
    }, 150);

    setTimeout(() => setFilaResaltada(null), 2500);
  };

  return (
    <div className="conteo-container">
      <div className="conteo-header">
        <h1>Conteo Cíclico</h1>

        <div className="conteo-badges">
          {pendientesSync > 0 && (
            <div className="badge-pendientes">{pendientesSync} conteo(s) por sincronizar</div>
          )}

          {pendientesSync > 0 && (
            <button
              type="button"
              className="btn-forzar-sync"
              onClick={forzarSincronizacion}
              disabled={isOffline}
              title={isOffline ? "Necesitas conexión para sincronizar" : "Reintenta el envío y muestra el error exacto si falla"}
            >
              Forzar Sincronización
            </button>
          )}

          <div className={`network-badge ${isOffline ? "badge-offline" : "badge-online"}`}>
            {isOffline ? (<><FaSignal /> Modo Offline</>) : (<><FaWifi /> Conectado</>)}
          </div>
        </div>
      </div>

      {mensaje && <div className="conteo-msg ok-msg">{mensaje}</div>}
      {error && <div className="conteo-msg error-msg">{error}</div>}

      <div className="barra">
        <select value={bodega} onChange={(e) => setBodega(e.target.value)}>
          <option value="">Seleccione Bodega</option>
          {bodegas.map((b) => (
            <option key={b.id} value={b.id}>
              {b.nombre}
            </option>
          ))}
        </select>

        <button
          onClick={crearAuditoria}
          disabled={!bodega || auditoria?.estado === "ABIERTA" || otrasAuditoriasAbiertas.length > 0}
          title={otrasAuditoriasAbiertas.length > 0 ? "Cierra o anula las auditorías abiertas de esta bodega primero" : undefined}
        >
          Crear Auditoría
        </button>

        <button
          className="btn-scan"
          onClick={abrirEscaner}
          disabled={!auditoria || auditoria.estado !== "ABIERTA"}
        >
          <FaCamera /> Escanear Código
        </button>

        {auditoria && (
          <div className={`estado-auditoria estado-${auditoria.estado.toLowerCase()}`}>
            Auditoría #{auditoria.id} - {auditoria.estado}
          </div>
        )}
      </div>

      {otrasAuditoriasAbiertas.length > 0 && (
        <div className="auditorias-abiertas-panel">
          <div className="auditorias-abiertas-header">
            <FaLockOpen /> Esta bodega ya tiene {otrasAuditoriasAbiertas.length} auditoría(s) abierta(s).
            Debes reanudarla(s) y cerrarla(s), o anularla(s), antes de crear una nueva.
          </div>

          {otrasAuditoriasAbiertas.map((a) => (
            <div key={a.id} className="auditoria-abierta-item">
              <span>
                Auditoría #{a.id} · {a.usuario_nombre || "usuario desconocido"} ·{" "}
                {a.fecha_inicio ? new Date(a.fecha_inicio).toLocaleString() : "sin fecha"}
              </span>

              <div className="auditoria-abierta-acciones">
                <button className="btn-reanudar" onClick={() => reanudarAuditoria(a)}>
                  <FaUndo /> Reanudar
                </button>
                <button className="btn-anular" onClick={() => anularAuditoriaAbierta(a.id)}>
                  <FaTimes /> Anular
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="guia-auditoria">
        <h2>Guía rápida para realizar una auditoría</h2>

        <div className="guia-grid">
          <div className="guia-card">
            <strong>1. Seleccionar bodega</strong>
            <p>Elija la bodega que desea revisar. El sistema cargará sus productos.</p>
          </div>

          <div className="guia-card">
            <strong>2. Crear auditoría</strong>
            <p>Presione “Crear Auditoría” (requiere conexión) para abrir un conteo oficial.</p>
          </div>

          <div className="guia-card">
            <strong>3. Recorrer y contar</strong>
            <p>Escriba la cantidad real o use “Escanear Código” para enfocar el producto con la cámara. Funciona sin señal.</p>
          </div>

          <div className="guia-card">
            <strong>4. Guardar conteo</strong>
            <p>Guarda las cantidades en este dispositivo y las sincroniza automáticamente al recuperar señal.</p>
          </div>

          <div className="guia-card">
            <strong>5. Cerrar auditoría</strong>
            <p>Requiere conexión y que todos los conteos estén sincronizados. Ya no se pueden modificar cantidades.</p>
          </div>

          <div className="guia-card">
            <strong>6. Ajustar stock</strong>
            <p>Actualiza el inventario real. Si hay faltantes en activos críticos o fuera de lo normal, se exige firma de un supervisor y se genera una alerta de posible pérdida.</p>
          </div>
        </div>
      </div>

      <div className="tabla-conteo-wrapper">
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Producto</th>
            <th>Sistema</th>
            <th>Conteo</th>
            <th>Diferencia</th>
          </tr>
        </thead>

        <tbody>
          {productos.length === 0 ? (
            <tr>
              <td colSpan="5" style={{ textAlign: "center", padding: "30px" }}>
                Seleccione una bodega para ver productos.
              </td>
            </tr>
          ) : (
            productos.map((p, index) => (
              <tr
                key={p.id}
                ref={(el) => { filaRefs.current[p.id] = el; }}
                className={filaResaltada === p.id ? "fila-resaltada" : ""}
              >
                <td>{p.codigo}</td>
                <td>
                  {p.nombre}
                  {p.es_activo_critico && (
                    <span className="tag-critico-inline" title="Activo crítico / alto valor">
                      <FaShieldAlt />
                    </span>
                  )}
                </td>
                <td>{p.stock_actual}</td>
                <td>
                  <input
                    ref={(el) => { inputRefs.current[p.id] = el; }}
                    type="number"
                    min="0"
                    value={p.stock_fisico}
                    disabled={!auditoria || auditoria.estado !== "ABIERTA"}
                    onChange={(e) => actualizarConteo(index, e.target.value)}
                  />
                </td>
                <td
                  className={
                    Number(p.diferencia) === 0
                      ? "ok"
                      : esDescuadreCritico(p)
                      ? "danger"
                      : Math.abs(Number(p.diferencia)) <= 2
                      ? "warning"
                      : "danger"
                  }
                >
                  {p.diferencia}
                  {esDescuadreCritico(p) && <FaExclamationTriangle style={{ marginLeft: 6 }} />}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      </div>

      <div className="acciones">
        <button
          onClick={guardarConteo}
          disabled={!auditoria || auditoria.estado !== "ABIERTA"}
        >
          Guardar Conteo
        </button>

        <button
          onClick={cerrarAuditoria}
          disabled={!auditoria || auditoria.estado !== "ABIERTA"}
        >
          Cerrar Auditoría
        </button>

        <button
          onClick={solicitarAjusteStock}
          disabled={!auditoria || auditoria.estado !== "CERRADA"}
        >
          Ajustar Stock
        </button>

        {auditoria?.estado === "ABIERTA" && (
          <button
            className="btn-anular"
            onClick={() => anularAuditoriaAbierta(auditoria.id)}
            title="Descarta esta auditoría y libera la bodega para crear una nueva. Úsalo si quedó trabada y no puedes cerrarla."
          >
            <FaTimes /> Anular esta Auditoría
          </button>
        )}
      </div>

      {scannerAbierto && (
        <div className="scanner-overlay" onClick={cerrarEscaner}>
          <div className="scanner-modal" onClick={(e) => e.stopPropagation()}>
            <div className="scanner-header">
              <span><FaCamera /> Escanear código de producto</span>
              <button className="btn-cerrar-modal" onClick={cerrarEscaner}><FaTimes /></button>
            </div>

            {scannerError && <div className="conteo-msg error-msg">{scannerError}</div>}

            <div id="qr-reader-conteo" className="qr-reader-box" />

            <p className="scanner-hint">Apunta la cámara al código de barras o QR del producto.</p>
          </div>
        </div>
      )}

      {mostrarFirma && (
        <div className="firma-overlay">
          <div className="firma-modal">
            <div className="firma-header">
              <FaShieldAlt /> Autorización de Supervisor Requerida
            </div>

            <p className="firma-desc">
              Este ajuste incluye descuadres críticos (activos de alto valor o faltantes fuera de lo normal).
              Un supervisor debe firmar para autorizar y continuar.
            </p>

            <div className="criticos-lista">
              {itemsCriticos.map((p) => (
                <div key={p.id} className="critico-item">
                  <FaExclamationTriangle />
                  <span>{p.nombre}: diferencia de {p.diferencia} unidades</span>
                </div>
              ))}
            </div>

            {errorFirma && <div className="conteo-msg error-msg">{errorFirma}</div>}

            <div className="firma-canvas-wrapper">
              <SignatureCanvas
                ref={sigCanvas}
                penColor="#001529"
                canvasProps={{ className: "firma-canvas" }}
              />
            </div>

            <div className="firma-acciones">
              <button className="btn-firma-confirmar" onClick={confirmarFirmaYAjustar}>
                <FaCheckCircle /> Confirmar y Ajustar Stock
              </button>
              <button className="btn-firma-limpiar" onClick={() => sigCanvas.current?.clear()}>
                Limpiar firma
              </button>
              <button className="btn-firma-cancelar" onClick={() => setMostrarFirma(false)}>
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConteoCiclico;
