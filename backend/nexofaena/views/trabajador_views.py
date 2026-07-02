from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.response import Response

from nexofaena.models.trabajador import Trabajador
from nexofaena.serializers.trabajador_serializer import TrabajadorSerializer
from nexofaena.permissions import IsAdministrador


class TrabajadorViewSet(viewsets.ModelViewSet):
    serializer_class = TrabajadorSerializer
    permission_classes = [IsAdministrador]

    def get_queryset(self):
        queryset = (
            Trabajador.objects
            .all()
            .order_by("apellido_paterno", "nombres")
        )

        buscar = self.request.GET.get("buscar")
        activo = self.request.GET.get("activo")

        if buscar:
            queryset = queryset.filter(
                Q(rut__icontains=buscar) |
                Q(nombres__icontains=buscar) |
                Q(apellido_paterno__icontains=buscar) |
                Q(apellido_materno__icontains=buscar) |
                Q(cargo__icontains=buscar)
            )

        if activo is not None:
            activo_bool = activo.lower() in ["true", "1", "si", "sí"]
            queryset = queryset.filter(activo=activo_bool)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(
            {
                "success": True,
                "message": "Trabajador creado correctamente.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
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
                "message": "Trabajador actualizado correctamente.",
                "data": serializer.data,
            }
        )

    def destroy(self, request, *args, **kwargs):
        trabajador = self.get_object()
        trabajador.activo = False
        trabajador.save(update_fields=["activo"])

        return Response(
            {
                "success": True,
                "message": "Trabajador desactivado correctamente.",
            },
            status=status.HTTP_200_OK,
        )