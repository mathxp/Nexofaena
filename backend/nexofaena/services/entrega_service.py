import logging
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from nexofaena.models.entrega import EntregaEPP, DetalleEntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.unidad_activo import UnidadActivo
from nexofaena.services.alerta_service import AlertaService
from nexofaena.services.dashboard_service import DashboardService

logger = logging.getLogger("nexofaena")


class EntregaService:
    """
    Concentra la lógica de negocio de entregas de EPP: descuento de stock,
    cálculo de vencimiento de vida útil (Regla Minera Teck) y devoluciones
    de activos diarios (radios y similares).
    """

    @staticmethod
    @transaction.atomic
    def crear_entrega(*, trabajador_id, usuario_id, bodega_id, detalles,
                       firma_base64=None, observacion="", estado="COMPLETADA"):
        if not trabajador_id or not usuario_id or not bodega_id:
            raise ValidationError("Trabajador, usuario y bodega son obligatorios.")

        if not detalles:
            raise ValidationError("Debe incluir al menos un producto entregado.")

        try:
            trabajador = Trabajador.objects.get(id=trabajador_id)
        except Trabajador.DoesNotExist:
            raise ValidationError("El trabajador no existe.")

        entrega = EntregaEPP.objects.create(
            trabajador_id=trabajador_id,
            usuario_id=usuario_id,
            bodega_id=bodega_id,
            firma_base64=firma_base64,
            observacion=observacion,
            estado=estado,
        )
        entrega.trabajador = trabajador  # evita re-consultar el trabajador por cada detalle

        hoy = timezone.now().date()

        for item in detalles:
            inventario_id = item.get("inventario")

            try:
                cantidad = Decimal(str(item.get("cantidad") or "0"))
            except (ArithmeticError, ValueError):
                raise ValidationError("Detalle inválido: producto o cantidad incorrecta.")

            if not inventario_id or cantidad <= 0:
                raise ValidationError("Detalle inválido: producto o cantidad incorrecta.")

            try:
                producto = Inventario.objects.select_for_update().get(
                    id=inventario_id,
                    bodega_id=bodega_id,
                )
            except Inventario.DoesNotExist:
                raise ValidationError("El producto no existe en la bodega seleccionada.")

            if producto.stock_actual < cantidad:
                raise ValidationError(f"Stock insuficiente para {producto.nombre}.")

            unidad_activo_id = item.get("unidad_activo")
            unidad = None

            if producto.es_devolutivo:
                if not unidad_activo_id:
                    raise ValidationError(
                        f"{producto.nombre} es un activo devolutivo: debe seleccionar una unidad específica."
                    )

                if cantidad != 1:
                    raise ValidationError(
                        f"Las unidades individuales de {producto.nombre} se entregan de a una."
                    )

                # No puede retirar un devolutivo nuevo mientras deba otro:
                # si no lo devuelve primero, no queda claro cuál de los dos
                # le corresponde devolver después, y el stock de devolutivos
                # queda descuadrado. Aplica parejo al kiosco de autoservicio
                # y a una entrega manual del bodeguero, porque ambos pasan
                # por este mismo servicio.
                tiene_pendiente = DetalleEntregaEPP.objects.filter(
                    entrega__trabajador_id=trabajador_id,
                    unidad_activo__isnull=False,
                    devuelto=False,
                ).exists()

                if tiene_pendiente:
                    raise ValidationError(
                        f"{trabajador.nombres} {trabajador.apellido_paterno} ya tiene un equipo devolutivo "
                        "pendiente de devolver. Debe devolverlo antes de retirar otro."
                    )

                try:
                    unidad = UnidadActivo.objects.select_for_update().get(
                        id=unidad_activo_id,
                        inventario_id=producto.id,
                    )
                except UnidadActivo.DoesNotExist:
                    raise ValidationError("La unidad seleccionada no existe para este producto.")

                if unidad.estado != "DISPONIBLE":
                    raise ValidationError(f"La unidad {unidad.codigo} no está disponible.")

                unidad.estado = "ENTREGADA"
                unidad.save(update_fields=["estado"])
            elif unidad_activo_id:
                raise ValidationError(f"{producto.nombre} no es un activo devolutivo, no admite unidad individual.")

            stock_anterior = producto.stock_actual
            nuevo_stock = stock_anterior - cantidad

            producto.stock_actual = nuevo_stock
            producto.save(update_fields=["stock_actual"])

            AlertaService.verificar_stock_producto(producto)

            fecha_vencimiento = None
            if producto.vida_util_dias is not None:
                fecha_vencimiento = hoy + timedelta(days=producto.vida_util_dias)

            detalle = DetalleEntregaEPP.objects.create(
                entrega=entrega,
                inventario=producto,
                cantidad=cantidad,
                talla=item.get("talla", ""),
                observacion=item.get("observacion", ""),
                fecha_vencimiento_vida_util=fecha_vencimiento,
                unidad_activo=unidad,
                precio_unitario=producto.precio_unitario,
            )

            if fecha_vencimiento:
                AlertaService.verificar_vencimiento_detalle(detalle)

            MovimientoInventario.objects.create(
                usuario_id=usuario_id,
                bodega_id=bodega_id,
                inventario=producto,
                entrega=entrega,
                trabajador_id=trabajador_id,
                tipo_movimiento="SALIDA",
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_actual=nuevo_stock,
                observacion=f"Entrega pañol #{entrega.id} - {observacion}",
            )

            logger.info(
                "Detalle entrega registrado | entrega_id=%s | producto=%s | cantidad=%s | "
                "stock_anterior=%s | stock_actual=%s",
                entrega.id, producto.nombre, cantidad, stock_anterior, nuevo_stock,
            )

        DashboardService.invalidar_cache()

        return entrega

    @staticmethod
    @transaction.atomic
    def registrar_devolucion(*, detalle_id, usuario_id, observacion="", estado_devolucion="OPERATIVA"):
        if estado_devolucion not in ("OPERATIVA", "DAÑADA"):
            raise ValidationError("Estado de devolución inválido: debe ser OPERATIVA o DAÑADA.")

        try:
            detalle = (
                DetalleEntregaEPP.objects
                .select_for_update(of=("self",))
                .select_related("inventario", "entrega", "entrega__bodega", "entrega__trabajador", "unidad_activo")
                .get(id=detalle_id)
            )
        except DetalleEntregaEPP.DoesNotExist:
            raise ValidationError("El detalle de entrega no existe.")

        if not detalle.inventario.es_devolutivo:
            raise ValidationError(f"{detalle.inventario.nombre} no es un activo devolutivo.")

        if detalle.devuelto:
            raise ValidationError("Este ítem ya fue registrado como devuelto.")

        unidad = None

        if detalle.unidad_activo:
            try:
                unidad = UnidadActivo.objects.select_for_update().get(id=detalle.unidad_activo_id)
            except UnidadActivo.DoesNotExist:
                raise ValidationError("La unidad asociada a esta entrega ya no existe.")

            # Si vuelve dañada, no queda disponible para reasignar hasta que
            # pase por mantención.
            unidad.estado = "EN_MANTENCION" if estado_devolucion == "DAÑADA" else "DISPONIBLE"
            unidad.save(update_fields=["estado"])

        producto = Inventario.objects.select_for_update().get(id=detalle.inventario_id)

        stock_anterior = producto.stock_actual
        nuevo_stock = stock_anterior + detalle.cantidad

        producto.stock_actual = nuevo_stock
        producto.save(update_fields=["stock_actual"])

        AlertaService.verificar_stock_producto(producto)

        detalle.devuelto = True
        detalle.fecha_devolucion = timezone.now()
        detalle.estado_devolucion = estado_devolucion
        detalle.save(update_fields=["devuelto", "fecha_devolucion", "estado_devolucion"])

        if detalle.fecha_vencimiento_vida_util:
            AlertaService.verificar_vencimiento_detalle(detalle)

        if estado_devolucion == "DAÑADA" and unidad:
            AlertaService.generar_alerta_mantenimiento(unidad, detalle)

        MovimientoInventario.objects.create(
            usuario_id=usuario_id,
            bodega_id=detalle.entrega.bodega_id,
            inventario=producto,
            entrega=detalle.entrega,
            trabajador_id=detalle.entrega.trabajador_id,
            tipo_movimiento="DEVOLUCION",
            cantidad=detalle.cantidad,
            stock_anterior=stock_anterior,
            stock_actual=nuevo_stock,
            observacion=(
                f"Devolución activo diario ({estado_devolucion}) - Entrega #{detalle.entrega_id} - {observacion}"
            ),
        )

        logger.info(
            "Devolución registrada | detalle_id=%s | producto=%s | estado=%s | stock_anterior=%s | stock_actual=%s",
            detalle.id, producto.nombre, estado_devolucion, stock_anterior, nuevo_stock,
        )

        DashboardService.invalidar_cache()

        return detalle
