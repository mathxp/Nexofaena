from decimal import Decimal
import logging

from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.response import Response

from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.permissions import IsBodeguero
from nexofaena.serializers.movimiento_inventario_serializer import MovimientoInventarioSerializer
from nexofaena.services.alerta_service import AlertaService


logger = logging.getLogger("nexofaena")


class MovimientoInventarioViewSet(viewsets.ModelViewSet):
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [IsBodeguero]

    def get_queryset(self):
        queryset = (
            MovimientoInventario.objects
            .select_related("bodega", "inventario", "trabajador", "usuario")
            .order_by("-fecha")
        )

        bodega = self.request.GET.get("bodega")
        inventario = self.request.GET.get("inventario")
        tipo = self.request.GET.get("tipo")

        if bodega:
            queryset = queryset.filter(bodega_id=bodega)

        if inventario:
            queryset = queryset.filter(inventario_id=inventario)

        if tipo:
            queryset = queryset.filter(tipo_movimiento=tipo)

        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if request.user.rol.nombre == "Supervisor":
            logger.warning(
                "Intento bloqueado de movimiento | usuario=%s | rol=%s",
                request.user.username,
                request.user.rol.nombre,
            )

            return Response(
                {"detail": "El Supervisor no puede registrar movimientos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        inventario_id = request.data.get("inventario")
        usuario_id = request.data.get("usuario")
        bodega_id = request.data.get("bodega")
        tipo = request.data.get("tipo_movimiento")
        cantidad = request.data.get("cantidad")
        observacion = request.data.get("observacion", "")

        if not inventario_id or not usuario_id or not bodega_id or not tipo or cantidad in ["", None]:
            logger.warning(
                "Movimiento rechazado por campos incompletos | usuario=%s | data=%s",
                request.user.username,
                request.data,
            )

            return Response(
                {"detail": "Faltan campos requeridos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cantidad = Decimal(str(cantidad))

        if cantidad <= 0:
            return Response(
                {"detail": "La cantidad debe ser mayor a cero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            producto = Inventario.objects.select_for_update().get(
                id=inventario_id,
                bodega_id=bodega_id,
            )
        except Inventario.DoesNotExist:
            logger.warning(
                "Movimiento rechazado: producto no existe | usuario=%s | inventario_id=%s | bodega_id=%s",
                request.user.username,
                inventario_id,
                bodega_id,
            )

            return Response(
                {"detail": "El producto no existe en la bodega seleccionada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stock_anterior = producto.stock_actual

        if tipo == "INGRESO":
            nuevo_stock = stock_anterior + cantidad

        elif tipo == "SALIDA":
            if stock_anterior < cantidad:
                logger.warning(
                    "Movimiento rechazado por stock insuficiente | usuario=%s | producto=%s | solicitado=%s | disponible=%s",
                    request.user.username,
                    producto.nombre,
                    cantidad,
                    stock_anterior,
                )

                return Response(
                    {"detail": "Stock insuficiente para realizar la salida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            nuevo_stock = stock_anterior - cantidad

        elif tipo == "AJUSTE":
            nuevo_stock = cantidad

        else:
            return Response(
                {"detail": "Tipo de movimiento inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        producto.stock_actual = nuevo_stock
        producto.save(update_fields=["stock_actual"])

        AlertaService.verificar_stock_producto(producto)

        movimiento = MovimientoInventario.objects.create(
            usuario_id=usuario_id,
            bodega_id=bodega_id,
            inventario=producto,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_actual=nuevo_stock,
            observacion=observacion,
        )

        logger.info(
            "Movimiento registrado | usuario=%s | tipo=%s | producto=%s | bodega_id=%s | cantidad=%s | stock_anterior=%s | stock_actual=%s",
            request.user.username,
            tipo,
            producto.nombre,
            bodega_id,
            cantidad,
            stock_anterior,
            nuevo_stock,
        )

        serializer = self.get_serializer(movimiento)

        return Response(
            {
                "success": True,
                "message": "Movimiento registrado correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        logger.warning(
            "Intento de eliminación de movimiento bloqueado | usuario=%s",
            request.user.username,
        )

        return Response(
            {
                "detail": "Los movimientos de inventario no pueden eliminarse por razones de auditoría."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )