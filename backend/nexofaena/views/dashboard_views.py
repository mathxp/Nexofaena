from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from nexofaena.models.alerta import Alerta
from nexofaena.permissions import IsBodeguero, IsSupervisor
from nexofaena.serializers.alerta_serializer import AlertaSerializer
from nexofaena.services.dashboard_service import DashboardService


class AlertaViewSet(viewsets.ModelViewSet):
    queryset = Alerta.objects.all().order_by("-fecha_alerta")
    serializer_class = AlertaSerializer
    permission_classes = [IsBodeguero]


class DashboardResumenView(APIView):
    permission_classes = [IsSupervisor]

    def get(self, request):
        try:
            return Response(
                DashboardService.obtener_dashboard(),
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Error al obtener el dashboard.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )