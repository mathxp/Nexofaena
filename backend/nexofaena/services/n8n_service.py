"""
Integración con n8n para la reposición automática al proveedor.

Flujo completo (ver docs/integraciones/n8n-reposicion.md):
1. Un producto entra en stock crítico -> AlertaService crea la Alerta
   STOCK_CRITICO (una sola vez por episodio: no se duplica mientras siga
   abierta) -> la señal post_save llama a notificar_stock_critico().
2. n8n recibe el aviso, busca el proveedor en Google Sheets, pide aprobación
   al supervisor y, si aprueba, envía la orden de compra.
3. n8n informa el resultado a /api/integraciones/n8n/alertas/<id>/resolver/
   -> registrar_resultado() deja la orden en el historial de alertas.
"""
import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from nexofaena.models.alerta import Alerta, TipoAlerta

logger = logging.getLogger("nexofaena")

TIMEOUT_SEGUNDOS = 8
ESTADOS_VALIDOS = {"aprobada", "rechazada"}


def armar_aviso_stock_critico(alerta):
    """Todo lo que n8n necesita para cotizar sin volver a consultar la API."""
    producto = alerta.inventario
    stock_actual = float(producto.stock_actual)
    stock_minimo = float(producto.stock_minimo)
    stock_maximo = float(producto.stock_maximo)
    precio = float(producto.precio_unitario)

    # Se repone hasta el máximo; si el producto no tiene máximo definido,
    # al doble del mínimo.
    objetivo = stock_maximo if stock_maximo > stock_minimo else stock_minimo * 2
    cantidad = max(objetivo - stock_actual, 1)

    return {
        "evento": "stock_critico",
        "alerta_id": alerta.id,
        "fecha": timezone.localtime(alerta.fecha_alerta).isoformat(),
        "producto": {
            "id": producto.id,
            "codigo": producto.codigo,
            "nombre": producto.nombre,
            "marca": producto.marca or "",
            "modelo": producto.modelo or "",
            "unidad_medida": producto.unidad_medida,
            "precio_unitario": precio,
        },
        "bodega": {"id": producto.bodega_id, "nombre": producto.bodega.nombre},
        "stock": {"actual": stock_actual, "minimo": stock_minimo, "maximo": stock_maximo},
        "reposicion": {
            "cantidad_sugerida": round(cantidad),
            "costo_estimado_clp": round(cantidad * precio),
            "tiempo_reposicion_dias": producto.tiempo_reposicion_dias or 7,
        },
        "mensaje": alerta.mensaje,
    }


def _enviar(aviso):
    cuerpo = json.dumps(aviso).encode("utf-8")
    peticion = urllib.request.Request(
        settings.N8N_WEBHOOK_URL,
        data=cuerpo,
        headers={"Content-Type": "application/json", "X-NexoFaena-Token": settings.N8N_TOKEN},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            return 200 <= respuesta.status < 300
    except (urllib.error.URLError, TimeoutError) as error:
        # n8n caído o mal configurado nunca debe afectar la entrega que
        # originó la alerta: se registra y sigue.
        logger.warning("No se pudo avisar a n8n (alerta %s): %s", aviso.get("alerta_id"), error)
        return False


def notificar_stock_critico(alerta, en_segundo_plano=True):
    """
    Envía el aviso a n8n. Se espera a que la transacción se confirme (si se
    revierte, no hubo stock crítico que avisar) y se envía en un hilo aparte:
    quien registró la entrega no tiene por qué esperar a n8n.
    """
    if alerta.tipo_alerta != TipoAlerta.STOCK_CRITICO or not alerta.inventario_id:
        return False
    if not settings.N8N_WEBHOOK_URL:
        return False

    aviso = armar_aviso_stock_critico(alerta)

    def despachar():
        if en_segundo_plano:
            threading.Thread(target=_enviar, args=(aviso,), daemon=True).start()
        else:
            _enviar(aviso)

    transaction.on_commit(despachar)
    return True


def registrar_resultado(alerta_id, estado, orden="", detalle="", aprobado_por=""):
    """
    n8n informa qué pasó con la reposición. La decisión se registra como una
    alerta de SISTEMA ya leída, para que quede en el historial de la bodega
    quién aprobó qué y cuándo. Solo una compra aprobada da por atendida la
    alerta original: si se rechaza, el producto sigue en stock crítico.
    """
    alerta = Alerta.objects.select_related("inventario", "bodega").filter(
        id=alerta_id, tipo_alerta=TipoAlerta.STOCK_CRITICO,
    ).first()
    if alerta is None:
        return None

    nombre = alerta.inventario.nombre if alerta.inventario else "producto"
    if estado == "aprobada":
        mensaje = f"Orden de compra {orden or 'sin número'} enviada al proveedor por {nombre}."
    else:
        mensaje = f"Reposición de {nombre} rechazada."
    if aprobado_por:
        mensaje += f" Decisión de {aprobado_por}."
    if detalle:
        mensaje += f" {detalle}"

    if estado == "aprobada":
        alerta.leida = True
        alerta.save(update_fields=["leida"])

    return Alerta.objects.create(
        inventario=alerta.inventario,
        bodega=alerta.bodega,
        tipo_alerta=TipoAlerta.SISTEMA,
        mensaje=mensaje[:1000],
        leida=True,
    )
