from decimal import Decimal
import logging

from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.permissions import IsBodeguero, IsEncargadoBodega
from nexofaena.serializers.movimiento_inventario_serializer import MovimientoInventarioSerializer
from nexofaena.services.alerta_service import AlertaService
from nexofaena.services.dashboard_service import DashboardService


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
        usuario_id = request.user.id
        bodega_id = request.data.get("bodega")
        tipo = request.data.get("tipo_movimiento")
        cantidad = request.data.get("cantidad")
        observacion = request.data.get("observacion", "")

        if not inventario_id or not bodega_id or not tipo or cantidad in ["", None]:
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

        # En AJUSTE la cantidad es "el nuevo stock exacto" (línea más abajo:
        # nuevo_stock = cantidad), no una cantidad a sumar/restar: 0 es un
        # valor legítimo (el producto se agotó por completo). En INGRESO y
        # SALIDA, en cambio, un movimiento de 0 unidades no representa nada.
        limite_minimo = Decimal("0") if tipo == "AJUSTE" else Decimal("0.01")

        if cantidad < limite_minimo:
            mensaje = (
                "La cantidad no puede ser negativa."
                if tipo == "AJUSTE"
                else "La cantidad debe ser mayor a cero."
            )
            return Response({"detail": mensaje}, status=status.HTTP_400_BAD_REQUEST)

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

        DashboardService.invalidar_cache()

        serializer = self.get_serializer(movimiento)

        return Response(
            {
                "success": True,
                "message": "Movimiento registrado correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], permission_classes=[IsEncargadoBodega])
    @transaction.atomic
    def traspaso(self, request, *args, **kwargs):
        """
        Traspaso entre bodegas (ej. Reserva -> Central): distinto de una
        entrega a trabajador. Mueve stock entre DOS filas de Inventario (una
        por bodega) y queda registrado en un único MovimientoInventario tipo
        TRASPASO con trazabilidad de ambos lados (origen y destino).
        """
        inventario_origen_id = request.data.get("inventario_origen")
        inventario_destino_id = request.data.get("inventario_destino")
        cantidad = request.data.get("cantidad")
        observacion = request.data.get("observacion", "")

        if not inventario_origen_id or not inventario_destino_id or cantidad in ["", None]:
            return Response(
                {"detail": "Faltan campos requeridos: inventario_origen, inventario_destino, cantidad."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cantidad = Decimal(str(cantidad))
        except (ArithmeticError, ValueError):
            return Response({"detail": "Cantidad inválida."}, status=status.HTTP_400_BAD_REQUEST)

        if cantidad <= 0:
            return Response({"detail": "La cantidad debe ser mayor a cero."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            origen = Inventario.objects.select_for_update().get(id=inventario_origen_id)
            destino = Inventario.objects.select_for_update().get(id=inventario_destino_id)
        except Inventario.DoesNotExist:
            return Response({"detail": "El producto de origen o destino no existe."}, status=status.HTTP_400_BAD_REQUEST)

        if origen.bodega_id == destino.bodega_id:
            return Response(
                {"detail": "El origen y el destino deben ser bodegas distintas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if origen.stock_actual < cantidad:
            return Response(
                {"detail": f"Stock insuficiente en {origen.bodega.nombre} para traspasar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stock_anterior_origen = origen.stock_actual
        stock_anterior_destino = destino.stock_actual

        origen.stock_actual = stock_anterior_origen - cantidad
        destino.stock_actual = stock_anterior_destino + cantidad
        origen.save(update_fields=["stock_actual"])
        destino.save(update_fields=["stock_actual"])

        AlertaService.verificar_stock_producto(origen)
        AlertaService.verificar_stock_producto(destino)

        movimiento = MovimientoInventario.objects.create(
            usuario=request.user,
            bodega_id=origen.bodega_id,
            inventario=origen,
            tipo_movimiento="TRASPASO",
            cantidad=cantidad,
            stock_anterior=stock_anterior_origen,
            stock_actual=origen.stock_actual,
            bodega_destino_id=destino.bodega_id,
            inventario_destino=destino,
            stock_anterior_destino=stock_anterior_destino,
            stock_actual_destino=destino.stock_actual,
            observacion=observacion or f"Traspaso {origen.bodega.nombre} -> {destino.bodega.nombre}",
        )

        logger.info(
            "Traspaso registrado | usuario=%s | producto=%s | %s -> %s | cantidad=%s",
            request.user.username, origen.nombre, origen.bodega.nombre, destino.bodega.nombre, cantidad,
        )

        DashboardService.invalidar_cache()

        serializer = self.get_serializer(movimiento)

        return Response(
            {
                "success": True,
                "message": f"Traspaso registrado: {cantidad} {origen.unidad_medida} de {origen.bodega.nombre} a {destino.bodega.nombre}.",
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

    def update(self, request, *args, **kwargs):
        # El modelo se documenta como "registro inmutable" (foto del stock en
        # ese instante), pero ModelViewSet expone PUT/PATCH por defecto y el
        # serializer no marca los campos como read_only: sin este bloqueo,
        # cualquier Bodeguero podía reescribir cantidad/stock_anterior/
        # stock_actual de un movimiento pasado sin que eso tocara el stock
        # real ni quedara trazado, rompiendo toda la auditoría del sistema.
        logger.warning(
            "Intento de edición de movimiento bloqueado | usuario=%s | movimiento_id=%s",
            request.user.username,
            kwargs.get("pk"),
        )

        return Response(
            {"detail": "Los movimientos de inventario no pueden editarse: son un registro inmutable."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)