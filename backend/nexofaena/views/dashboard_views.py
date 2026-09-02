from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from nexofaena.models.alerta import Alerta
from nexofaena.permissions import IsBodeguero, IsSupervisor
from nexofaena.serializers.alerta_serializer import AlertaSerializer
from nexofaena.services.dashboard_service import DashboardService
from nexofaena.services.ml_service import MLService


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


class MLAnalyticsView(APIView):
    """
    Bloque de IA extendido del Dashboard Gerencial: reglas de asociación
    de EPP (cross-selling) y perfil de riesgo operativo por trabajador
    (Random Forest Classifier). Separado de DashboardResumenView para no
    encarecer la carga del dashboard base con estos dos modelos.
    """
    permission_classes = [IsSupervisor]

    def get(self, request):
        try:
            return Response(
                DashboardService.obtener_ml_avanzado(),
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Error al obtener el módulo de IA avanzado.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MLBusquedaView(APIView):
    """
    Buscador semántico en texto plano para el Dashboard Gerencial
    (ej. "consumo de cascos"): TF-IDF + similitud de coseno sobre el
    catálogo de inventario, con fallback a difflib. Sin caché: es una
    consulta puntual por texto libre, no un bloque fijo del dashboard.
    """
    permission_classes = [IsSupervisor]

    def get(self, request):
        consulta = request.GET.get("q", "")

        try:
            return Response(
                MLService.buscar_kpi_por_texto(consulta),
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Error al ejecutar la búsqueda.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )