from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.response import Response

from nexofaena.models.inventario import Inventario
from nexofaena.permissions import IsBodeguero
from nexofaena.serializers.inventario_serializer import InventarioSerializer


class InventarioViewSet(viewsets.ModelViewSet):
    serializer_class = InventarioSerializer
    permission_classes = [IsBodeguero]

    def get_queryset(self):
        queryset = (
            Inventario.objects
            .select_related("bodega")
            .all()
            .order_by("nombre")
        )

        bodega = self.request.GET.get("bodega")
        estado = self.request.GET.get("estado")
        buscar = self.request.GET.get("buscar")
        necesita_reposicion = self.request.GET.get("reposicion")

        if bodega:
            queryset = queryset.filter(bodega_id=bodega)

        if estado is not None:
            estado_bool = estado.lower() in ["true", "1", "si", "sí"]
            queryset = queryset.filter(estado=estado_bool)

        if buscar:
            queryset = queryset.filter(
                Q(codigo__icontains=buscar) |
                Q(nombre__icontains=buscar) |
                Q(descripcion__icontains=buscar) |
                Q(marca__icontains=buscar)
            )

        if necesita_reposicion is not None:
            reposicion = necesita_reposicion.lower() in ["true", "1", "si", "sí"]

            if reposicion:
                queryset = [
                    producto
                    for producto in queryset
                    if producto.necesita_reposicion
                ]

        return queryset

    def create(self, request, *args, **kwargs):
        if request.user.rol.nombre not in ["Administrador", "Bodeguero"]:
            return Response(
                {"detail": "No tiene permisos para crear productos de inventario."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(
            {
                "success": True,
                "message": "Producto creado correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        if request.user.rol.nombre not in ["Administrador", "Bodeguero"]:
            return Response(
                {"detail": "No tiene permisos para modificar productos de inventario."},
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
                "message": "Producto actualizado correctamente.",
                "data": serializer.data,
            }
        )

    def destroy(self, request, *args, **kwargs):
        if request.user.rol.nombre != "Administrador":
            return Response(
                {"detail": "Solo el administrador puede desactivar productos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        producto = self.get_object()
        producto.estado = False
        producto.save(update_fields=["estado"])

        return Response(
            {
                "success": True,
                "message": "Producto desactivado correctamente.",
            },
            status=status.HTTP_200_OK,
        )