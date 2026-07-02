from django.core.exceptions import ValidationError

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.response import Response
from nexofaena.models.auditoria_inventario import AuditoriaInventario
from nexofaena.permissions import IsBodeguero
from nexofaena.serializers.auditoria_serializer import AuditoriaSerializer
from nexofaena.services.auditoria_service import AuditoriaInventarioService


class AuditoriaInventarioViewSet(viewsets.ModelViewSet):
    serializer_class = AuditoriaSerializer
    permission_classes = [IsBodeguero]

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

    @action(detail=True, methods=["post"])
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

    @action(detail=True, methods=["post"])
    def ajustar_stock(self, request, pk=None):
        if request.user.rol.nombre not in ["Administrador", "Supervisor"]:
            return Response(
                {"detail": "Solo Administrador o Supervisor pueden aprobar ajustes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            auditoria = AuditoriaInventarioService.ajustar_stock(
                auditoria_id=pk,
                usuario=request.user,
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
                "detalle": data,
            }
        )