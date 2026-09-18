from django.db.models import Q
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from nexofaena.models.trabajador import Trabajador
from nexofaena.models.bodega import Bodega
from nexofaena.serializers.trabajador_serializer import TrabajadorSerializer
from nexofaena.services.alerta_service import AlertaService
from nexofaena.permissions import IsAdministrador, IsBodeguero

# face-api.js (modelo face_recognition_model) siempre entrega vectores de
# exactamente 128 floats: cualquier otro largo es un descriptor corrupto o
# de otra librería, no un dato válido para guardar.
LARGO_DESCRIPTOR_FACIAL = 128


class TrabajadorViewSet(viewsets.ModelViewSet):
    serializer_class = TrabajadorSerializer

    def get_permissions(self):
        # Gestionar la ficha (crear/editar/desactivar) sigue siendo solo de
        # Administrador (así lo ve el frontend: "Personal" en el menú es
        # exclusivo de ese rol). Pero LEER la lista es una dependencia real
        # de otros roles: el Dashboard normal la usa para el conteo de
        # trabajadores activos y Entregas Pañol la necesita para elegir a
        # quién se le entrega el EPP, y ambos módulos sí son accesibles
        # para Bodeguero/Supervisor/Operador. enrolar_rostro también: lo
        # dispara el reconocimiento facial de Entregas Pañol (mismo nivel
        # de acceso que registrar una entrega, no requiere Administrador).
        if self.action in ("enrolar_rostro", "reportar_suplantacion"):
            return [IsBodeguero()]
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdministrador()]

    @action(detail=True, methods=["post"], url_path="enrolar-rostro")
    def enrolar_rostro(self, request, pk=None):
        """
        Guarda el descriptor facial capturado en el kiosco (autoenrolamiento
        la primera vez que un trabajador no reconocido se identifica por
        RUT). No crea trabajadores nuevos: solo le agrega el rostro a una
        ficha que ya existe, para no poder inventar una identidad desde el
        kiosco sin pasar antes por el alta real en Personal.
        """
        trabajador = self.get_object()
        descriptor = request.data.get("face_descriptor")

        if (
            not isinstance(descriptor, list)
            or len(descriptor) != LARGO_DESCRIPTOR_FACIAL
            or not all(isinstance(v, (int, float)) for v in descriptor)
        ):
            return Response(
                {"detail": f"face_descriptor debe ser un arreglo de {LARGO_DESCRIPTOR_FACIAL} números."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trabajador.face_descriptor = descriptor
        trabajador.face_enrolado_en = timezone.now()
        trabajador.save(update_fields=["face_descriptor", "face_enrolado_en"])

        return Response({
            "success": True,
            "message": f"Rostro de {trabajador.nombres} {trabajador.apellido_paterno} enrolado correctamente.",
        })

    @action(detail=True, methods=["post"], url_path="reportar-suplantacion")
    def reportar_suplantacion(self, request, pk=None):
        """
        Entregas Pañol llama esto cuando el rostro coincide con este
        trabajador pero el chequeo de vida (parpadeo) falló varias veces
        seguidas: alguien podría estar mostrando una foto en vez de
        presentarse en persona. Crea una Alerta, que dispara el bot de
        Telegram automáticamente (ver notificacion_service.py).
        """
        trabajador = self.get_object()
        bodega = Bodega.objects.filter(id=request.data.get("bodega")).first()

        AlertaService.generar_alerta_suplantacion(trabajador, bodega=bodega)

        return Response({"success": True, "message": "Alerta de posible suplantación registrada."})

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