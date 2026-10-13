import math

from django.db import transaction
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

# Mismo umbral que usa el kiosco para reconocer (UMBRAL_DISTANCIA_FACIAL en
# useReconocimientoFacial.jsx): si el kiosco tomaría este rostro como el de
# otra persona, tampoco se puede registrar a nombre de alguien más.
UMBRAL_DISTANCIA_ROSTRO_DUPLICADO = 0.6


def _dueno_del_rostro(descriptor, excluir_id):
    """Devuelve el trabajador activo (distinto de excluir_id) cuyo rostro
    registrado se parece a este descriptor, o None."""
    candidatos = (
        Trabajador.objects
        .filter(face_descriptor__isnull=False, activo=True)
        .exclude(id=excluir_id)
        .only("id", "nombres", "apellido_paterno", "rut", "face_descriptor")
    )

    mas_cercano, menor_distancia = None, UMBRAL_DISTANCIA_ROSTRO_DUPLICADO
    for candidato in candidatos:
        guardado = candidato.face_descriptor
        if not isinstance(guardado, list) or len(guardado) != LARGO_DESCRIPTOR_FACIAL:
            continue
        distancia = math.dist(descriptor, guardado)
        if distancia < menor_distancia:
            mas_cercano, menor_distancia = candidato, distancia

    return mas_cercano


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
        if self.action == "reiniciar_rostro":
            return [IsAdministrador()]
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

        Como el RUT no es secreto, el kiosco por sí solo no prueba que quien
        se registra sea el dueño de la ficha. Por eso:
        - solo se registra si la ficha aún no tiene rostro (cambiarlo es
          reiniciar_rostro, exclusivo de Administrador);
        - se rechaza un rostro que ya pertenece a otro trabajador;
        - cada registro exitoso genera una alerta para que el bodeguero lo
          confirme.
        """
        descriptor = request.data.get("face_descriptor")

        if (
            not isinstance(descriptor, list)
            or len(descriptor) != LARGO_DESCRIPTOR_FACIAL
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in descriptor)
        ):
            return Response(
                {"detail": f"face_descriptor debe ser un arreglo de {LARGO_DESCRIPTOR_FACIAL} números."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bodega = Bodega.objects.filter(id=request.data.get("bodega")).first()

        with transaction.atomic():
            # select_for_update: dos kioscos enrolando a la misma persona a la
            # vez no pueden pasar ambos el chequeo de "aún no tiene rostro".
            trabajador = Trabajador.objects.select_for_update().filter(pk=self.kwargs["pk"]).first()
            if trabajador is None:
                return Response({"detail": "Trabajador no encontrado."}, status=status.HTTP_404_NOT_FOUND)

            if trabajador.face_descriptor:
                AlertaService.generar_alerta_reenrolamiento_bloqueado(trabajador, bodega=bodega)
                return Response(
                    {
                        "detail": (
                            "Este trabajador ya tiene un rostro registrado. Si la cámara no te "
                            "reconoce, pide a un administrador que reinicie tu rostro."
                        ),
                        "codigo": "ROSTRO_YA_REGISTRADO",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            dueno = _dueno_del_rostro(descriptor, excluir_id=trabajador.id)
            if dueno is not None:
                AlertaService.generar_alerta_rostro_duplicado(trabajador, dueno, bodega=bodega)
                return Response(
                    {
                        "detail": "Este rostro ya está registrado a nombre de otro trabajador.",
                        "codigo": "ROSTRO_DE_OTRO_TRABAJADOR",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            trabajador.face_descriptor = descriptor
            trabajador.face_enrolado_en = timezone.now()
            trabajador.save(update_fields=["face_descriptor", "face_enrolado_en"])

        AlertaService.generar_alerta_enrolamiento(trabajador, bodega=bodega)

        return Response({
            "success": True,
            "message": f"Rostro de {trabajador.nombres} {trabajador.apellido_paterno} enrolado correctamente.",
        })

    @action(detail=True, methods=["post"], url_path="reiniciar-rostro")
    def reiniciar_rostro(self, request, pk=None):
        """Borra el rostro registrado para que el trabajador vuelva a
        enrolarse en el kiosco (cambio de aspecto, o un registro hecho por
        otra persona). Solo Administrador: es la única forma de reemplazar un
        rostro, así que no puede estar al alcance del propio kiosco."""
        trabajador = self.get_object()
        trabajador.face_descriptor = None
        trabajador.face_enrolado_en = None
        trabajador.save(update_fields=["face_descriptor", "face_enrolado_en"])

        return Response({
            "success": True,
            "message": f"Rostro de {trabajador.nombres} {trabajador.apellido_paterno} reiniciado. Puede volver a registrarse en el kiosco.",
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