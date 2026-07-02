from decimal import Decimal
import logging

from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from nexofaena.models.entrega import EntregaEPP, DetalleEntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.serializers.entrega_serializer import EntregaEPPSerializer
from nexofaena.services.alerta_service import AlertaService


logger = logging.getLogger("nexofaena")


class EntregaEPPViewSet(viewsets.ModelViewSet):
    serializer_class = EntregaEPPSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            EntregaEPP.objects
            .select_related("trabajador", "usuario", "bodega")
            .prefetch_related("detalles__inventario")
            .all()
            .order_by("-fecha_entrega")
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        trabajador_id = request.data.get("trabajador")
        usuario_id = request.data.get("usuario")
        bodega_id = request.data.get("bodega")
        firma_base64 = request.data.get("firma_base64")
        observacion = request.data.get("observacion", "")
        estado = request.data.get("estado", "COMPLETADA")
        detalles = request.data.get("detalles", [])

        if not trabajador_id or not usuario_id or not bodega_id:
            logger.warning(
                "Entrega rechazada por campos incompletos | usuario=%s | data=%s",
                request.user.username,
                request.data,
            )

            return Response(
                {"detail": "Trabajador, usuario y bodega son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not detalles:
            logger.warning(
                "Entrega rechazada sin detalles | usuario=%s | trabajador_id=%s",
                request.user.username,
                trabajador_id,
            )

            return Response(
                {"detail": "Debe incluir al menos un producto entregado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entrega = EntregaEPP.objects.create(
            trabajador_id=trabajador_id,
            usuario_id=usuario_id,
            bodega_id=bodega_id,
            firma_base64=firma_base64,
            observacion=observacion,
            estado=estado,
        )

        logger.info(
            "Entrega creada | entrega_id=%s | trabajador_id=%s | usuario=%s | bodega_id=%s",
            entrega.id,
            trabajador_id,
            request.user.username,
            bodega_id,
        )

        for item in detalles:
            inventario_id = item.get("inventario")
            cantidad = Decimal(str(item.get("cantidad", "0")))

            if not inventario_id or cantidad <= 0:
                logger.warning(
                    "Detalle de entrega inválido | entrega_id=%s | item=%s",
                    entrega.id,
                    item,
                )

                return Response(
                    {"detail": "Detalle inválido: producto o cantidad incorrecta."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                producto = Inventario.objects.select_for_update().get(
                    id=inventario_id,
                    bodega_id=bodega_id,
                )
            except Inventario.DoesNotExist:
                logger.warning(
                    "Entrega rechazada: producto no existe | entrega_id=%s | inventario_id=%s | bodega_id=%s",
                    entrega.id,
                    inventario_id,
                    bodega_id,
                )

                return Response(
                    {"detail": "El producto no existe en la bodega seleccionada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if producto.stock_actual < cantidad:
                logger.warning(
                    "Entrega rechazada por stock insuficiente | entrega_id=%s | producto=%s | solicitado=%s | disponible=%s",
                    entrega.id,
                    producto.nombre,
                    cantidad,
                    producto.stock_actual,
                )

                return Response(
                    {"detail": f"Stock insuficiente para {producto.nombre}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            stock_anterior = producto.stock_actual
            nuevo_stock = stock_anterior - cantidad

            producto.stock_actual = nuevo_stock
            producto.save(update_fields=["stock_actual"])

            AlertaService.verificar_stock_producto(producto)

            DetalleEntregaEPP.objects.create(
                entrega=entrega,
                inventario=producto,
                cantidad=cantidad,
                talla=item.get("talla", ""),
                observacion=item.get("observacion", ""),
            )

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
                "Detalle entrega registrado | entrega_id=%s | usuario=%s | producto=%s | cantidad=%s | stock_anterior=%s | stock_actual=%s",
                entrega.id,
                request.user.username,
                producto.nombre,
                cantidad,
                stock_anterior,
                nuevo_stock,
            )

        serializer = self.get_serializer(entrega)

        return Response(
            {
                "success": True,
                "message": "Entrega registrada correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )