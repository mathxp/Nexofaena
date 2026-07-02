from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from nexofaena.models.auditoria_inventario import (
    AuditoriaInventario,
    DetalleAuditoriaInventario,
)
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario


class AuditoriaInventarioService:

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

        stock_fisico_decimal = Decimal(str(stock_fisico))

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
            auditoria = AuditoriaInventario.objects.get(
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
    def ajustar_stock(auditoria_id, usuario):
        try:
            auditoria = AuditoriaInventario.objects.get(
                id=auditoria_id,
                estado="CERRADA",
            )
        except AuditoriaInventario.DoesNotExist:
            raise ValidationError(
                "Solo se puede ajustar stock de una auditoría cerrada."
            )

        detalles = (
            DetalleAuditoriaInventario.objects
            .filter(auditoria=auditoria)
            .select_related("inventario")
        )

        for detalle in detalles:
            if detalle.diferencia == 0:
                continue

            producto = Inventario.objects.select_for_update().get(
                pk=detalle.inventario.pk
            )

            stock_anterior = producto.stock_actual
            nuevo_stock = detalle.stock_fisico

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

        return auditoria