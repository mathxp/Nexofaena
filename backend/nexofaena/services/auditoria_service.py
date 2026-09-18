from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from nexofaena.models.auditoria_inventario import (
    AuditoriaInventario,
    DetalleAuditoriaInventario,
)
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.services.alerta_service import AlertaService
from nexofaena.services.dashboard_service import DashboardService

# Un faltante se considera "crítico" (exige firma de supervisor y genera
# alerta de posible pérdida) si supera este porcentaje del stock del sistema,
# o si el producto está marcado como activo de alto valor.
UMBRAL_DESCUADRE_PORCENTAJE = Decimal("0.2")


class AuditoriaInventarioService:

    @staticmethod
    def _es_descuadre_critico(detalle):
        if detalle.diferencia >= 0:
            return False

        if detalle.inventario.es_activo_critico:
            return True

        if detalle.stock_sistema > 0:
            return abs(detalle.diferencia) / detalle.stock_sistema > UMBRAL_DESCUADRE_PORCENTAJE

        return False

    @staticmethod
    @transaction.atomic
    def crear_auditoria(bodega_id, usuario, observacion=""):
        auditoria_abierta = AuditoriaInventario.objects.filter(
            bodega_id=bodega_id,
            estado="ABIERTA",
        ).first()

        if auditoria_abierta:
            raise ValidationError(
                "Ya existe una auditoría abierta para esta bodega."
            )

        auditoria = AuditoriaInventario.objects.create(
            bodega_id=bodega_id,
            usuario=usuario,
            observacion=observacion,
        )

        return auditoria

    @staticmethod
    @transaction.atomic
    def registrar_conteo(
        auditoria_id,
        inventario_id,
        stock_fisico,
        observacion="",
    ):
        try:
            auditoria = AuditoriaInventario.objects.get(
                id=auditoria_id,
                estado="ABIERTA",
            )
        except AuditoriaInventario.DoesNotExist:
            raise ValidationError(
                "La auditoría no existe o ya está cerrada."
            )

        try:
            producto = Inventario.objects.get(
                id=inventario_id,
                bodega=auditoria.bodega,
            )
        except Inventario.DoesNotExist:
            raise ValidationError(
                "El producto no pertenece a esta bodega."
            )

        if stock_fisico in (None, ""):
            raise ValidationError(
                "El stock físico es requerido."
            )

        try:
            stock_fisico_decimal = Decimal(str(stock_fisico))
        except InvalidOperation:
            raise ValidationError(
                f"El stock físico '{stock_fisico}' no es un número válido."
            )

        if stock_fisico_decimal < 0:
            raise ValidationError(
                "El stock físico no puede ser negativo."
            )

        stock_sistema = producto.stock_actual
        diferencia = stock_fisico_decimal - stock_sistema

        detalle, _ = DetalleAuditoriaInventario.objects.update_or_create(
            auditoria=auditoria,
            inventario=producto,
            defaults={
                "stock_sistema": stock_sistema,
                "stock_fisico": stock_fisico_decimal,
                "diferencia": diferencia,
                "observacion": observacion,
            },
        )

        return detalle

    @staticmethod
    @transaction.atomic
    def cerrar_auditoria(auditoria_id):
        try:
            auditoria = AuditoriaInventario.objects.select_for_update().get(
                id=auditoria_id,
                estado="ABIERTA",
            )
        except AuditoriaInventario.DoesNotExist:
            raise ValidationError(
                "La auditoría no existe o ya está cerrada."
            )

        auditoria.estado = "CERRADA"
        auditoria.fecha_cierre = timezone.now()
        auditoria.save(update_fields=["estado", "fecha_cierre"])

        return auditoria

    @staticmethod
    @transaction.atomic
    def anular_auditoria(auditoria_id):
        """
        Descarta una auditoría abierta sin tocar stock (ej. se abrió por error,
        quedó abandonada, o es un registro de prueba). Libera la bodega para
        poder abrir una auditoría nueva, ya que solo se permite una ABIERTA
        por bodega a la vez.
        """
        try:
            auditoria = AuditoriaInventario.objects.select_for_update().get(
                id=auditoria_id,
                estado="ABIERTA",
            )
        except AuditoriaInventario.DoesNotExist:
            raise ValidationError(
                "La auditoría no existe o ya no está abierta."
            )

        auditoria.estado = "ANULADA"
        auditoria.fecha_cierre = timezone.now()
        auditoria.save(update_fields=["estado", "fecha_cierre"])

        return auditoria

    @staticmethod
    @transaction.atomic
    def ajustar_stock(auditoria_id, usuario, firma_autorizacion=None):
        try:
            auditoria = AuditoriaInventario.objects.select_for_update().get(
                id=auditoria_id,
                estado="CERRADA",
            )
        except AuditoriaInventario.DoesNotExist:
            raise ValidationError(
                "Solo se puede ajustar stock de una auditoría cerrada."
            )

        detalles = list(
            DetalleAuditoriaInventario.objects
            .filter(auditoria=auditoria)
            .select_related("inventario")
        )

        detalles_criticos = [d for d in detalles if AuditoriaInventarioService._es_descuadre_critico(d)]

        if detalles_criticos and not firma_autorizacion:
            raise ValidationError(
                "Esta auditoría tiene descuadres críticos (faltantes en activos de alto valor o "
                "sobre el umbral normal). Se requiere firma de autorización de un supervisor para ajustar el stock."
            )

        for detalle in detalles:
            if detalle.diferencia == 0:
                continue

            producto = Inventario.objects.select_for_update().get(
                pk=detalle.inventario.pk
            )

            stock_anterior = producto.stock_actual
            # OJO: no se puede fijar stock_actual = detalle.stock_fisico. Ese
            # valor es una foto de cuando se hizo el conteo; si entre el
            # conteo y este ajuste hubo ingresos/salidas reales, sobrescribir
            # con el número viejo los borra en silencio. Se aplica en cambio
            # la diferencia detectada sobre el stock vigente ahora mismo.
            nuevo_stock = max(Decimal("0"), stock_anterior + detalle.diferencia)

            producto.stock_actual = nuevo_stock
            producto.save(update_fields=["stock_actual"])

            MovimientoInventario.objects.create(
                usuario=usuario,
                bodega=auditoria.bodega,
                inventario=producto,
                tipo_movimiento="AJUSTE",
                cantidad=abs(detalle.diferencia),
                stock_anterior=stock_anterior,
                stock_actual=nuevo_stock,
                observacion=f"Ajuste por conteo cíclico auditoría #{auditoria.pk}",
            )

            if detalle in detalles_criticos:
                AlertaService.generar_alerta_descuadre(
                    producto=producto,
                    bodega=auditoria.bodega,
                    diferencia=detalle.diferencia,
                    auditoria_id=auditoria.pk,
                )

        if detalles_criticos:
            auditoria.firma_autorizacion = firma_autorizacion
            auditoria.autorizado_por = usuario

        # Sin esta transición, la auditoría seguía viéndose "CERRADA" después
        # de ajustar: el filtro de arriba (estado="CERRADA") volvía a
        # encontrarla, permitiendo aplicar la misma diferencia dos veces
        # sobre el stock si alguien apretaba "Ajustar stock" otra vez.
        auditoria.estado = "AJUSTADA"
        auditoria.save(update_fields=["estado", "firma_autorizacion", "autorizado_por"])

        DashboardService.invalidar_cache()

        return auditoria