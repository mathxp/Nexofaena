from django.db import transaction
from django.core.exceptions import ValidationError

from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario


class InventarioService:
    @staticmethod
    @transaction.atomic
    def registrar_salida(inventario_id, cantidad, usuario, trabajador=None, observacion=""):
        try:
            producto = Inventario.objects.select_for_update().get(id=inventario_id)
        except Inventario.DoesNotExist:
            raise ValidationError("El producto no existe en el inventario.")

        if producto.stock_actual < cantidad:
            raise ValidationError(
                f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock_actual}"
            )

        stock_anterior = producto.stock_actual

        producto.stock_actual -= cantidad
        producto.save(update_fields=["stock_actual"])

        MovimientoInventario.objects.create(
            usuario=usuario,
            bodega=producto.bodega,
            inventario=producto,
            trabajador=trabajador,
            tipo_movimiento="SALIDA",
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_actual=producto.stock_actual,
            observacion=observacion,
        )

        return producto