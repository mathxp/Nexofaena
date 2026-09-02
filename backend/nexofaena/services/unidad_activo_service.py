from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from nexofaena.models.entrega import DetalleEntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.unidad_activo import UnidadActivo
from nexofaena.services.alerta_service import AlertaService
from nexofaena.services.dashboard_service import DashboardService


class UnidadActivoService:
    """
    Gestiona el alta y baja de unidades individuales de productos devolutivos
    (ej. cada radio de comunicación), manteniendo sincronizado el stock
    agregado del producto en Inventario.
    """

    @staticmethod
    @transaction.atomic
    def crear_unidad(inventario_id, codigo, usuario):
        try:
            producto = Inventario.objects.select_for_update().get(id=inventario_id)
        except Inventario.DoesNotExist:
            raise ValidationError("El producto no existe.")

        if not producto.es_devolutivo:
            raise ValidationError(f"{producto.nombre} no está marcado como activo devolutivo.")

        codigo = (codigo or "").strip().upper()
        if not codigo:
            raise ValidationError("El código de unidad es obligatorio.")

        if UnidadActivo.objects.filter(codigo=codigo).exists():
            raise ValidationError(f"Ya existe una unidad con el código {codigo}.")

        try:
            unidad = UnidadActivo.objects.create(inventario=producto, codigo=codigo)
        except IntegrityError:
            raise ValidationError(f"Ya existe una unidad con el código {codigo}.")

        stock_anterior = producto.stock_actual
        producto.stock_actual += 1
        producto.save(update_fields=["stock_actual"])

        MovimientoInventario.objects.create(
            usuario=usuario,
            bodega=producto.bodega,
            inventario=producto,
            tipo_movimiento="INGRESO",
            cantidad=1,
            stock_anterior=stock_anterior,
            stock_actual=producto.stock_actual,
            observacion=f"Alta de unidad devolutiva {codigo}",
        )

        AlertaService.verificar_stock_producto(producto)
        DashboardService.invalidar_cache()

        return unidad

    @staticmethod
    @transaction.atomic
    def dar_de_baja(unidad_id, usuario):
        try:
            unidad = UnidadActivo.objects.select_for_update().get(id=unidad_id)
        except UnidadActivo.DoesNotExist:
            raise ValidationError("La unidad no existe.")

        if unidad.estado == "ENTREGADA":
            raise ValidationError("No puede dar de baja una unidad que está entregada. Regístrala como devuelta primero.")

        if unidad.estado == "DE_BAJA":
            raise ValidationError("Esta unidad ya está dada de baja.")

        producto = Inventario.objects.select_for_update().get(id=unidad.inventario_id)

        stock_anterior = producto.stock_actual
        producto.stock_actual = max(producto.stock_actual - 1, 0)
        producto.save(update_fields=["stock_actual"])

        MovimientoInventario.objects.create(
            usuario=usuario,
            bodega=producto.bodega,
            inventario=producto,
            tipo_movimiento="AJUSTE",
            cantidad=1,
            stock_anterior=stock_anterior,
            stock_actual=producto.stock_actual,
            observacion=f"Baja de unidad devolutiva {unidad.codigo}",
        )

        unidad.estado = "DE_BAJA"
        unidad.save(update_fields=["estado"])

        AlertaService.verificar_stock_producto(producto)
        DashboardService.invalidar_cache()

        return unidad

    @staticmethod
    @transaction.atomic
    def marcar_reparada(unidad_id):
        """
        Cierra el ciclo de mantención: una unidad que volvió DAÑADA queda
        disponible de nuevo para asignarse. No mueve stock (ya se contaba
        como en bodega desde que se devolvió), solo cambia su estado y
        cierra la alerta de mantenimiento asociada.
        """
        try:
            unidad = UnidadActivo.objects.select_for_update().get(id=unidad_id)
        except UnidadActivo.DoesNotExist:
            raise ValidationError("La unidad no existe.")

        if unidad.estado != "EN_MANTENCION":
            raise ValidationError("Esta unidad no está en mantención.")

        unidad.estado = "DISPONIBLE"
        unidad.save(update_fields=["estado"])

        detalle = (
            DetalleEntregaEPP.objects
            .filter(unidad_activo_id=unidad_id, estado_devolucion="DAÑADA")
            .order_by("-fecha_devolucion")
            .first()
        )

        if detalle:
            AlertaService._cerrar_alerta(
                detalle.alertas.filter(tipo_alerta="MANTENIMIENTO", leida=False).first()
            )

        return unidad
