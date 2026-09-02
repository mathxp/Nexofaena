from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.services.alerta_service import AlertaService
from nexofaena.services.dashboard_service import DashboardService


class DespachoRapidoService:
    """
    Despacho de consumibles de alta rotación (ej. agua) con un clic: sin
    trabajador, sin RUT ni firma. Reutiliza el mismo MovimientoInventario de
    tipo SALIDA que el resto del sistema para no crear un modelo paralelo.
    """

    @staticmethod
    @transaction.atomic
    def despachar(*, inventario_id, cantidad, usuario, bodega_id):
        try:
            producto = Inventario.objects.select_for_update().get(
                id=inventario_id,
                bodega_id=bodega_id,
            )
        except Inventario.DoesNotExist:
            raise ValidationError("El producto no existe en la bodega seleccionada.")

        if not producto.es_despacho_rapido:
            raise ValidationError(f"{producto.nombre} no está habilitado para despacho rápido.")

        try:
            cantidad_decimal = Decimal(str(cantidad or "1"))
        except (ArithmeticError, ValueError):
            raise ValidationError("Cantidad inválida.")

        if cantidad_decimal <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero.")

        if producto.stock_actual < cantidad_decimal:
            raise ValidationError(f"Stock insuficiente para {producto.nombre}.")

        stock_anterior = producto.stock_actual
        nuevo_stock = stock_anterior - cantidad_decimal

        producto.stock_actual = nuevo_stock
        producto.save(update_fields=["stock_actual"])

        movimiento = MovimientoInventario.objects.create(
            usuario=usuario,
            bodega_id=bodega_id,
            inventario=producto,
            tipo_movimiento="SALIDA",
            cantidad=cantidad_decimal,
            stock_anterior=stock_anterior,
            stock_actual=nuevo_stock,
            observacion="Despacho rápido (sin RUT ni firma)",
        )

        AlertaService.verificar_stock_producto(producto)
        DashboardService.invalidar_cache()

        return movimiento

    @staticmethod
    def obtener_estadisticas(bodega_id=None):
        """
        Contador simple (no predictivo) de consumo hoy/semana por producto de
        despacho rápido, en vez de las predicciones complejas de ml_service.
        """
        hoy = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        inicio_semana = hoy - timedelta(days=hoy.weekday())

        productos = Inventario.objects.filter(es_despacho_rapido=True, estado=True).select_related("bodega")
        if bodega_id:
            productos = productos.filter(bodega_id=bodega_id)

        movimientos_base = MovimientoInventario.objects.filter(
            tipo_movimiento="SALIDA",
            inventario__es_despacho_rapido=True,
        )
        if bodega_id:
            movimientos_base = movimientos_base.filter(bodega_id=bodega_id)

        consumo_hoy = {
            fila["inventario_id"]: float(fila["total"] or 0)
            for fila in movimientos_base.filter(fecha__gte=hoy).values("inventario_id").annotate(total=Sum("cantidad"))
        }
        consumo_semana = {
            fila["inventario_id"]: float(fila["total"] or 0)
            for fila in movimientos_base.filter(fecha__gte=inicio_semana).values("inventario_id").annotate(total=Sum("cantidad"))
        }

        return [
            {
                "inventario_id": p.id,
                "producto_nombre": p.nombre,
                "codigo": p.codigo,
                "bodega": p.bodega_id,
                "bodega_nombre": p.bodega.nombre,
                "stock_actual": float(p.stock_actual),
                "consumo_hoy": consumo_hoy.get(p.id, 0),
                "consumo_semana": consumo_semana.get(p.id, 0),
            }
            for p in productos
        ]
