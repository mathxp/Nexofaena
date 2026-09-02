from django.core.exceptions import ValidationError

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nexofaena.models.unidad_activo import UnidadActivo
from nexofaena.permissions import IsBodeguero
from nexofaena.serializers.unidad_activo_serializer import UnidadActivoSerializer
from nexofaena.services.unidad_activo_service import UnidadActivoService


class UnidadActivoViewSet(viewsets.ModelViewSet):
    serializer_class = UnidadActivoSerializer
    permission_classes = [IsBodeguero]

    def get_queryset(self):
        queryset = (
            UnidadActivo.objects
            .select_related("inventario", "inventario__bodega")
            .all()
        )

        inventario = self.request.GET.get("inventario")
        bodega = self.request.GET.get("bodega")
        estado = self.request.GET.get("estado")

        if inventario:
            queryset = queryset.filter(inventario_id=inventario)

        if bodega:
            queryset = queryset.filter(inventario__bodega_id=bodega)

        if estado:
            queryset = queryset.filter(estado=estado)

        return queryset

    def create(self, request, *args, **kwargs):
        try:
            unidad = UnidadActivoService.crear_unidad(
                inventario_id=request.data.get("inventario"),
                codigo=request.data.get("codigo", ""),
                usuario=request.user,
            )
        except ValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(unidad)

        return Response(
            {
                "success": True,
                "message": "Unidad creada correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        try:
            UnidadActivoService.dar_de_baja(unidad_id=kwargs["pk"], usuario=request.user)
        except ValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"success": True, "message": "Unidad dada de baja correctamente."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reparar(self, request, pk=None):
        try:
            unidad = UnidadActivoService.marcar_reparada(unidad_id=pk)
        except ValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(unidad)

        return Response(
            {
                "success": True,
                "message": "Unidad marcada como reparada y disponible.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
