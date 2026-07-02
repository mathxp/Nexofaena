import { useEffect, useState } from "react";
import api from "../../api";
import "./ConteoCiclico.css";

const ConteoCiclico = () => {
  const [bodegas, setBodegas] = useState([]);
  const [bodega, setBodega] = useState("");
  const [productos, setProductos] = useState([]);
  const [auditoria, setAuditoria] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    cargarBodegas();
  }, []);

  useEffect(() => {
    if (bodega) {
      cargarProductos();
      setAuditoria(null);
      setMensaje("");
      setError("");
    }
  }, [bodega]);

  const cargarBodegas = async () => {
    try {
      const res = await api.get("/bodegas/");
      setBodegas(res.data);
    } catch {
      setError("No se pudieron cargar las bodegas.");
    }
  };

  const cargarProductos = async () => {
    try {
      const res = await api.get(`/inventario/?bodega=${bodega}`);

      const lista = res.data.map((p) => ({
        ...p,
        stock_fisico: p.stock_actual,
        diferencia: 0,
      }));

      setProductos(lista);
    } catch {
      setError("No se pudo cargar el inventario de la bodega.");
    }
  };

  const crearAuditoria = async () => {
    if (!bodega) {
      setError("Primero debe seleccionar una bodega.");
      return;
    }

    try {
      const res = await api.post("/auditorias-inventario/", {
        bodega,
        observacion: "Conteo cíclico",
      });

      setAuditoria(res.data.data);
      setMensaje("Auditoría creada correctamente. Ahora ingrese el conteo físico.");
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo crear la auditoría.");
    }
  };

  const actualizarConteo = (index, valor) => {
    const copia = [...productos];

    copia[index].stock_fisico = valor;
    copia[index].diferencia =
      Number(valor || 0) - Number(copia[index].stock_actual || 0);

    setProductos(copia);
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
        await api.post(
          `/auditorias-inventario/${auditoria.id}/registrar_conteo/`,
          {
            inventario: producto.id,
            stock_fisico: producto.stock_fisico,
          }
        );
      }

      setMensaje("Conteo guardado correctamente. Ahora puede cerrar la auditoría.");
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo guardar el conteo.");
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

    try {
      const res = await api.post(
        `/auditorias-inventario/${auditoria.id}/cerrar/`
      );

      setAuditoria(res.data.data);
      setMensaje("Auditoría cerrada correctamente. Ahora puede ajustar stock.");
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo cerrar la auditoría.");
    }
  };

  const ajustarStock = async () => {
    if (!auditoria) {
      setError("Primero debe crear una auditoría.");
      return;
    }

    if (auditoria.estado !== "CERRADA") {
      setError("Debe cerrar la auditoría antes de ajustar stock.");
      return;
    }

    try {
      await api.post(
        `/auditorias-inventario/${auditoria.id}/ajustar_stock/`
      );

      setMensaje("Stock actualizado correctamente según conteo físico.");
      setError("");
      cargarProductos();
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo ajustar el stock.");
    }
  };

  return (
    <div className="conteo-container">
      <h1>Conteo Cíclico</h1>

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
          disabled={!bodega || auditoria?.estado === "ABIERTA"}
        >
          Crear Auditoría
        </button>

        {auditoria && (
          <div className={`estado-auditoria estado-${auditoria.estado.toLowerCase()}`}>
            Auditoría #{auditoria.id} - {auditoria.estado}
          </div>
        )}
      </div>

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
              <tr key={p.id}>
                <td>{p.codigo}</td>
                <td>{p.nombre}</td>
                <td>{p.stock_actual}</td>
                <td>
                  <input
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
                      : Math.abs(Number(p.diferencia)) <= 2
                      ? "warning"
                      : "danger"
                  }
                >
                  {p.diferencia}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

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
          onClick={ajustarStock}
          disabled={!auditoria || auditoria.estado !== "CERRADA"}
        >
          Ajustar Stock
        </button>
      </div>

      <div className="guia-auditoria">
        <h2>Guía rápida para realizar una auditoría</h2>

        <div className="guia-grid">
          <div className="guia-card">
            <strong>1. Seleccionar bodega</strong>
            <p>Elija la bodega que desea revisar. El sistema cargará sus productos.</p>
          </div>

          <div className="guia-card">
            <strong>2. Crear auditoría</strong>
            <p>Presione “Crear Auditoría” para abrir un conteo oficial.</p>
          </div>

          <div className="guia-card">
            <strong>3. Ingresar conteo físico</strong>
            <p>Revise producto por producto y escriba la cantidad real encontrada.</p>
          </div>

          <div className="guia-card">
            <strong>4. Guardar conteo</strong>
            <p>Guarda todas las cantidades contadas y calcula diferencias.</p>
          </div>

          <div className="guia-card">
            <strong>5. Cerrar auditoría</strong>
            <p>Cierra el conteo. Después de esto ya no se pueden modificar cantidades.</p>
          </div>

          <div className="guia-card">
            <strong>6. Ajustar stock</strong>
            <p>Actualiza el inventario del sistema según el conteo físico registrado.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConteoCiclico;