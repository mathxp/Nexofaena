# Reposición automática con n8n

> **Integración temporal de evaluación.** Se armó para una evaluación del ramo usando la prueba gratuita de n8n Cloud (14 días, desde el 31-10-2026). No se contratará n8n después. Para desactivarla, basta con borrar `N8N_WEBHOOK_URL` y `N8N_TOKEN` en Render: sin esas variables NexoFaena no envía nada y la ruta de respuesta devuelve 404. El resto del sistema no depende de esto.

Cuando un producto entra en **stock crítico**, NexoFaena avisa a n8n y el flujo:

1. busca el proveedor y el precio en **Google Sheets**,
2. le pide aprobación al supervisor por **Gmail** (botones Aprobar / Rechazar),
3. si aprueba, envía la orden de compra al proveedor por **Gmail**, avisa al equipo por **Telegram** y la registra en **Google Sheets**,
4. informa el resultado a **NexoFaena**, que cierra la alerta y deja la orden en el historial.

Plataformas integradas: NexoFaena, Google Sheets, Gmail y Telegram.

> Se probó primero con WhatsApp (Twilio), pero el modo de prueba actual de Twilio solo permite enviar plantillas aprobadas por WhatsApp (error "ContentSid Required"). Telegram no tiene esa restricción y NexoFaena ya tiene su bot.

```
NexoFaena ──(stock crítico)──▶ Webhook ─▶ Sheets: buscar proveedor ─▶ Gmail: pedir aprobación
                                                                          │
                                                ┌──────── aprobada ───────┴──────── rechazada ───────┐
                                                ▼                                                     ▼
                         Gmail: orden al proveedor · Telegram · Sheets: registrar          Sheets: registrar
                                                ▼                                                     ▼
                                     NexoFaena: resolver (aprobada)                     NexoFaena: resolver (rechazada)
```

---

## 1. Qué hace NexoFaena (ya está programado)

**Aviso a n8n.** Al crearse una alerta de stock crítico (una sola vez por episodio: no se repite mientras la alerta siga abierta), se envía un `POST` a `N8N_WEBHOOK_URL` con el header `X-NexoFaena-Token: <N8N_TOKEN>` y este cuerpo:

```json
{
  "evento": "stock_critico",
  "alerta_id": 128,
  "fecha": "2026-10-31T16:35:26-03:00",
  "producto": { "id": 12, "codigo": "RM-0003", "nombre": "Guantes de nitrilo", "marca": "Vinilo Chile",
                "modelo": "Nitrilo", "unidad_medida": "PAR", "precio_unitario": 1490.0 },
  "bodega": { "id": 1, "nombre": "Bodega Central" },
  "stock": { "actual": 8.0, "minimo": 20.0, "maximo": 45.0 },
  "reposicion": { "cantidad_sugerida": 37, "costo_estimado_clp": 55130, "tiempo_reposicion_dias": 7 },
  "mensaje": "Guantes de nitrilo está con stock crítico. Stock actual: 8. Stock mínimo: 20."
}
```

**Respuesta de n8n.** `POST /api/integraciones/n8n/alertas/<alerta_id>/resolver/` con el mismo header `X-NexoFaena-Token` y:

```json
{ "estado": "aprobada", "orden": "OC-0042", "aprobado_por": "Supervisor", "detalle": "Proveedor: Distribuidora Seguridad Norte" }
```

- `aprobada`: la alerta queda atendida y la orden se registra en el historial de Alertas.
- `rechazada`: se registra la decisión, pero la alerta sigue abierta (el stock sigue crítico).

**Comando de prueba** (envía un aviso real a n8n con un producto del inventario, sin tocar la base):

```powershell
cd backend
$env:N8N_WEBHOOK_URL = "https://<tu-n8n>/webhook-test/nexofaena-stock-critico"
$env:N8N_TOKEN = "<la-misma-clave-que-en-n8n>"
..\.venv\Scripts\python.exe manage.py probar_n8n
```

`--solo-mostrar` imprime el JSON sin enviarlo; `--codigo RM-0003` elige el producto.

---

## 2. Preparar las cuentas

1. **n8n Cloud** (prueba de 14 días): crea la cuenta en n8n.io.
2. **Clave compartida**: inventa una clave larga (ej. 32 caracteres al azar). Es el `N8N_TOKEN`.
3. **Google Sheets**: crea una planilla con dos hojas:
   - `Proveedores`: importa `docs/integraciones/proveedores.csv` (Archivo → Importar).
   - `Ordenes`: con los encabezados `fecha, orden, producto, cantidad, proveedor, total_clp, estado, alerta_id`.
4. **Telegram**: se usa el mismo bot de NexoFaena. Necesitas su token (`TELEGRAM_BOT_TOKEN` en Render) y el chat donde avisar: el grupo de alertas (`TELEGRAM_CHAT_ID`) o tu ID personal (pídelo a @userinfobot). En n8n usa solo la acción *Send a text message*: **no** agregues un nodo *Telegram Trigger* con este bot, porque le cambiaría el webhook y el bot de NexoFaena dejaría de responder.

---

## 3. Armar el flujo en n8n (nodo por nodo)

Los nombres entre comillas son los que aparecen en n8n. Usa *Execute step* en cada nodo para ver sus datos de salida antes de seguir.

### 1) Webhook — "Stock crítico NexoFaena"
- HTTP Method: `POST`
- Path: `nexofaena-stock-critico`
- Authentication: **Header Auth** → credencial nueva con Name `X-NexoFaena-Token` y Value = tu `N8N_TOKEN`.
- Respond: *Immediately*.

Toca **Listen for test event** y corre `manage.py probar_n8n` con la **Test URL**: deberías ver el JSON del aviso. Los datos quedan en `{{ $json.body }}`.

### 2) Google Sheets — "Buscar proveedor"
- Operation: **Get Row(s)** · Document: tu planilla · Sheet: `Proveedores`
- Filters → Column `producto` · Value `{{ $json.body.producto.nombre }}`

### 3) Code — "Armar orden"
Calcula el número de orden y el total con el precio acordado (o el precio de NexoFaena si el producto no está en la planilla):

```javascript
const aviso = $('Stock crítico NexoFaena').first().json.body;
const proveedor = $input.first().json;
const precio = Number(proveedor.precio_acordado_clp || aviso.producto.precio_unitario);
const cantidad = aviso.reposicion.cantidad_sugerida;

return [{
  json: {
    alerta_id: aviso.alerta_id,
    orden: `OC-${aviso.alerta_id}-${Date.now().toString().slice(-4)}`,
    producto: aviso.producto.nombre,
    bodega: aviso.bodega.nombre,
    stock_actual: aviso.stock.actual,
    stock_minimo: aviso.stock.minimo,
    cantidad,
    unidad: aviso.producto.unidad_medida,
    proveedor: proveedor.proveedor || 'Proveedor por definir',
    correo_proveedor: proveedor.correo_proveedor || '',
    dias_entrega: proveedor.dias_entrega || aviso.reposicion.tiempo_reposicion_dias,
    total_clp: Math.round(precio * cantidad),
  },
}];
```

### 4) Gmail — "Pedir aprobación al supervisor"
- Operation: **Send and Wait for Approval**
- To: correo del supervisor
- Subject: `Aprobar compra: {{ $json.cantidad }} {{ $json.unidad }} de {{ $json.producto }}`
- Message:
  ```
  {{ $json.producto }} está en stock crítico en {{ $json.bodega }}
  (quedan {{ $json.stock_actual }}, mínimo {{ $json.stock_minimo }}).

  Orden propuesta {{ $json.orden }}: {{ $json.cantidad }} {{ $json.unidad }}
  a {{ $json.proveedor }} por ${{ $json.total_clp }} CLP, entrega en {{ $json.dias_entrega }} días.
  ```
- Approval Options → Type of Approval: **Approve and Disapprove** · Approve Button Label `Aprobar compra` · Disapprove Button Label `Rechazar`.

### 5) IF — "¿Aprobada?"
- Condición: Boolean `{{ $json.data.approved }}` *is true*.
- ⚠️ Verifica el nombre del campo: corre el flujo una vez, aprueba desde el correo y mira la salida del nodo de Gmail. Si el campo se llama distinto, ajusta la condición.

### 6a) Rama "true" (aprobada)
1. **Gmail — "Orden al proveedor"** · Operation *Send* · To `{{ $('Armar orden').first().json.correo_proveedor }}` · Subject `Orden de compra {{ $('Armar orden').first().json.orden }} — RentaMaq` · Message con producto, cantidad, total y bodega de entrega.
2. **Telegram — "Avisar al equipo"** · Operation *Send a text message* · Chat ID = grupo de alertas o tu ID · Additional Fields → *Append n8n Attribution* desactivado · Text:
   ```
   ✅ Compra aprobada
   {{ $('Armar orden').first().json.cantidad }} {{ $('Armar orden').first().json.unidad }} de {{ $('Armar orden').first().json.producto }}
   Orden: {{ $('Armar orden').first().json.orden }}
   Proveedor: {{ $('Armar orden').first().json.proveedor }}
   Total: ${{ $('Armar orden').first().json.total_clp }} CLP
   Entrega en {{ $('Armar orden').first().json.dias_entrega }} días
   ```
3. **Google Sheets — "Registrar orden"** · Operation **Append Row** · Sheet `Ordenes` · mapea las columnas desde `Armar orden` con `estado = aprobada`.
4. **HTTP Request — "Informar a NexoFaena"**
   - Method `POST` · URL `https://nexofaena.onrender.com/api/integraciones/n8n/alertas/{{ $('Armar orden').first().json.alerta_id }}/resolver/`
   - Header `X-NexoFaena-Token` = tu `N8N_TOKEN`
   - Body JSON: `{ "estado": "aprobada", "orden": "{{ $('Armar orden').first().json.orden }}", "aprobado_por": "Supervisor", "detalle": "Proveedor: {{ $('Armar orden').first().json.proveedor }}" }`

### 6b) Rama "false" (rechazada)
1. **Google Sheets — "Registrar rechazo"** · Append Row con `estado = rechazada`.
2. **HTTP Request — "Informar rechazo"** · igual al anterior con `"estado": "rechazada"`.

---

## 4. Conectar con producción

1. En n8n, **activa (publica) el flujo** y copia la **Production URL** del Webhook (la Test URL solo funciona mientras el editor está escuchando).
2. En Render → servicio `nexofaena` → **Environment**, agrega:
   - `N8N_WEBHOOK_URL` = la Production URL
   - `N8N_TOKEN` = la misma clave del header
3. Guarda (Render redespliega solo).

---

## 5. Demostración en vivo

1. En NexoFaena registra una salida (Movimientos o Entregas) que deje un producto **bajo su mínimo**.
2. Llega el correo de aprobación al supervisor → **Aprobar compra**.
3. Llegan el aviso de Telegram y el correo al proveedor, y aparece la fila en `Ordenes`.
4. En NexoFaena → **Alertas**: la alerta de stock crítico queda atendida y aparece el registro de la orden.

Si el aviso no llega, revisa en n8n la pestaña **Executions** y en Render los logs (`No se pudo avisar a n8n ...`).
