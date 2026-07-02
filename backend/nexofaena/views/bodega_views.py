from rest_framework import status, viewsets
from rest_framework.response import Response

from nexofaena.models.bodega import Bodega
from nexofaena.permissions import IsBodeguero
from nexofaena.serializers.bodega_serializer import BodegaSerializer


class BodegaViewSet(viewsets.ModelViewSet):
    serializer_class = BodegaSerializer
    permission_classes = [IsBodeguero]

    def get_queryset(self):
        return Bodega.objects.all().order_by("nombre")

    def create(self, request, *args, **kwargs):
        if request.user.rol.nombre != "Administrador":
            return Response(
                {"detail": "No tiene permisos para crear bodegas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(
            {
                "success": True,
                "message": "Bodega creada correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        if request.user.rol.nombre != "Administrador":
            return Response(
                {"detail": "No tiene permisos para modificar bodegas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )

        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {
                "success": True,
                "message": "Bodega actualizada correctamente.",
                "data": serializer.data,
            }
        )

    def destroy(self, request, *args, **kwargs):
        if request.user.rol.nombre != "Administrador":
            return Response(
                {"detail": "No tiene permisos para eliminar bodegas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        bodega = self.get_object()
        bodega.estado = False
        bodega.save(update_fields=["estado"])

        return Response(
            {
                "success": True,
                "message": "Bodega desactivada correctamente.",
            },
            status=status.HTTP_200_OK,
        )