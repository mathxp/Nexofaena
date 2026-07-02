from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nexofaena.models.alerta import Alerta
from nexofaena.serializers.alerta_serializer import AlertaSerializer
from nexofaena.services.dashboard_service import DashboardService


class AlertaViewSet(viewsets.ModelViewSet):
    """
    CRUD de Alertas.

    La lógica de negocio (generación automática de alertas,
    reglas de criticidad, etc.) pertenece al AlertaService.
    """

    queryset = Alerta.objects.all().order_by("-fecha_alerta")
    serializer_class = AlertaSerializer
    permission_classes = [IsAuthenticated]


class DashboardResumenView(APIView):
    """
    Dashboard General.

    El frontend realiza una única petición:
        GET /api/dashboard/

    Toda la información proviene del DashboardService.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            dashboard = DashboardService.obtener_dashboard()

            return Response(
                dashboard,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Error al obtener el dashboard.",
                    "error": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )