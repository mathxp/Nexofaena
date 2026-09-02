import logging

from django.core.exceptions import ValidationError

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from nexofaena.models.entrega import EntregaEPP, DetalleEntregaEPP
from nexofaena.permissions import IsBodeguero
from nexofaena.serializers.entrega_serializer import EntregaEPPSerializer, DetalleEntregaEPPSerializer
from nexofaena.services.entrega_service import EntregaService


logger = logging.getLogger("nexofaena")


class EntregaEPPViewSet(viewsets.ModelViewSet):
    serializer_class = EntregaEPPSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            EntregaEPP.objects
            .select_related("trabajador", "usuario", "bodega")
            .prefetch_related("detalles__inventario", "detalles__unidad_activo")
            .all()
            .order_by("-fecha_entrega")
        )

    def create(self, request, *args, **kwargs):
        data = request.data

        try:
            entrega = EntregaService.crear_entrega(
                trabajador_id=data.get("trabajador"),
                usuario_id=request.user.id,
                bodega_id=data.get("bodega"),
                firma_base64=data.get("firma_base64"),
                observacion=data.get("observacion", ""),
                estado=data.get("estado", "COMPLETADA"),
                detalles=data.get("detalles", []),
            )
        except ValidationError as e:
            logger.warning(
                "Entrega rechazada | usuario=%s | data=%s | error=%s",
                request.user.username,
                data,
                e.messages,
            )

            return Response(
                {"detail": " ".join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Entrega creada | entrega_id=%s | usuario=%s",
            entrega.id,
            request.user.username,
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


class DetalleEntregaEPPViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Expone los ítems entregados para el Módulo de Devoluciones
    (activos diarios como radios de comunicación).
    """

    serializer_class = DetalleEntregaEPPSerializer
    permission_classes = [IsBodeguero]

    def get_queryset(self):
        queryset = (
            DetalleEntregaEPP.objects
            .select_related("inventario", "entrega", "entrega__trabajador", "entrega__bodega", "unidad_activo")
            .filter(unidad_activo__isnull=False)
        )

        bodega = self.request.GET.get("bodega")
        pendientes = self.request.GET.get("pendientes")

        if bodega:
            queryset = queryset.filter(entrega__bodega_id=bodega)

        if pendientes is not None:
            es_pendiente = pendientes.lower() in ["true", "1", "si", "sí"]
            queryset = queryset.filter(devuelto=not es_pendiente)

            if not es_pendiente:
                return queryset.order_by("-fecha_devolucion")

        return queryset.order_by("-entrega__fecha_entrega")

    @action(detail=True, methods=["post"])
    def devolver(self, request, pk=None):
        try:
            detalle = EntregaService.registrar_devolucion(
                detalle_id=pk,
                usuario_id=request.user.id,
                observacion=request.data.get("observacion", ""),
                estado_devolucion=request.data.get("estado_devolucion", "OPERATIVA"),
            )
        except ValidationError as e:
            return Response(
                {"detail": " ".join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Devolución registrada | detalle_id=%s | usuario=%s",
            detalle.id,
            request.user.username,
        )

        serializer = self.get_serializer(detalle)

        return Response(
            {
                "success": True,
                "message": "Devolución registrada correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
