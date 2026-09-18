import logging

from django.core.exceptions import ValidationError

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from nexofaena.models.auditoria_inventario import AuditoriaInventario
from nexofaena.permissions import IsBodeguero, IsEncargadoBodega
from nexofaena.serializers.auditoria_serializer import AuditoriaSerializer
from nexofaena.services.auditoria_service import AuditoriaInventarioService

logger = logging.getLogger("nexofaena")


class AuditoriaInventarioViewSet(viewsets.ModelViewSet):
    serializer_class = AuditoriaSerializer
    permission_classes = [IsBodeguero]

    def update(self, request, *args, **kwargs):
        # Todo cambio de estado (cerrar/anular/ajustar) tiene reglas de
        # negocio propias en AuditoriaInventarioService (una sola ABIERTA por
        # bodega, firma de supervisor si hay descuadre crítico, etc.). Sin
        # este bloqueo, ModelViewSet permitía un PATCH directo de "estado"
        # que se saltaba esas validaciones (ej. reabrir una auditoría ya
        # ajustada, o cerrar una sin haber contado nada).
        logger.warning(
            "Intento de edición directa de auditoría bloqueado | usuario=%s | auditoria_id=%s",
            request.user.username,
            kwargs.get("pk"),
        )

        return Response(
            {"detail": "Una auditoría no se edita directamente: usa cerrar/anular/ajustar-stock."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Borrar una auditoría se lleva en cascada sus DetalleAuditoriaInventario
        # (evidencia de descuadres ya usada para ajustar stock). No hay
        # razón de negocio para eliminar ese historial.
        logger.warning(
            "Intento de eliminación de auditoría bloqueado | usuario=%s | auditoria_id=%s",
            request.user.username,
            kwargs.get("pk"),
        )

        return Response(
            {"detail": "Las auditorías no pueden eliminarse por razones de trazabilidad: usa anular."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_queryset(self):
        queryset = (
            AuditoriaInventario.objects
            .select_related("bodega", "usuario")
            .prefetch_related("detalles__inventario")
            .all()
            .order_by("-fecha_inicio")
        )

        bodega = self.request.GET.get("bodega")
        estado = self.request.GET.get("estado")

        if bodega:
            queryset = queryset.filter(bodega_id=bodega)

        if estado:
            queryset = queryset.filter(estado=estado)

        return queryset

    def create(self, request, *args, **kwargs):
        try:
            auditoria = AuditoriaInventarioService.crear_auditoria(
                bodega_id=request.data.get("bodega"),
                usuario=request.user,
                observacion=request.data.get("observacion", ""),
            )

            serializer = self.get_serializer(auditoria)

            return Response(
                {
                    "success": True,
                    "message": "Auditoría de inventario creada correctamente.",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def registrar_conteo(self, request, pk=None):
        try:
            detalle = AuditoriaInventarioService.registrar_conteo(
                auditoria_id=pk,
                inventario_id=request.data.get("inventario"),
                stock_fisico=request.data.get("stock_fisico"),
                observacion=request.data.get("observacion", ""),
            )

            return Response(
                {
                    "success": True,
                    "message": "Conteo registrado correctamente.",
                    "data": {
                        "id": detalle.pk,
                        "inventario": detalle.inventario.pk,
                        "stock_sistema": detalle.stock_sistema,
                        "stock_fisico": detalle.stock_fisico,
                        "diferencia": detalle.diferencia,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Cualquier excepción no prevista debe llegar al frontend como JSON
            # interpretable (con detail) en vez de un 500 sin cuerpo, para que
            # la sincronización offline pueda mostrar el motivo real del fallo.
            return Response(
                {"detail": f"Error inesperado al registrar el conteo: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], permission_classes=[IsEncargadoBodega])
    def cerrar(self, request, pk=None):
        try:
            auditoria = AuditoriaInventarioService.cerrar_auditoria(pk)
            serializer = self.get_serializer(auditoria)

            return Response(
                {
                    "success": True,
                    "message": "Auditoría cerrada correctamente.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], permission_classes=[IsEncargadoBodega])
    def anular(self, request, pk=None):
        try:
            auditoria = AuditoriaInventarioService.anular_auditoria(pk)
            serializer = self.get_serializer(auditoria)

            return Response(
                {
                    "success": True,
                    "message": "Auditoría anulada correctamente.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], permission_classes=[IsEncargadoBodega])
    def ajustar_stock(self, request, pk=None):
        try:
            auditoria = AuditoriaInventarioService.ajustar_stock(
                auditoria_id=pk,
                usuario=request.user,
                firma_autorizacion=request.data.get("firma_autorizacion"),
            )

            serializer = self.get_serializer(auditoria)

            return Response(
                {
                    "success": True,
                    "message": "Stock ajustado correctamente según conteo físico.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        

    @action(detail=True, methods=["get"])
    def detalle(self, request, pk=None):
        auditoria = self.get_object()

        detalles = auditoria.detalles.select_related(
            "inventario"
        ).all()

        data = []

        for d in detalles:

            data.append(
                {
                    "producto": d.inventario.nombre,
                    "codigo": d.inventario.codigo,
                    "stock_sistema": d.stock_sistema,
                    "stock_fisico": d.stock_fisico,
                    "diferencia": d.diferencia,
                    "observacion": d.observacion,
                }
            )

        return Response(
            {
                "auditoria": auditoria.id,
                "estado": auditoria.estado,
                "fecha_inicio": auditoria.fecha_inicio,
                "fecha_cierre": auditoria.fecha_cierre,
                "firma_autorizacion": auditoria.firma_autorizacion,
                "autorizado_por_nombre": auditoria.autorizado_por.username if auditoria.autorizado_por else None,
                "detalle": data,
            }
        )