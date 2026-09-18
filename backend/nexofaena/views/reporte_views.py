from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from nexofaena.permissions import IsBodeguero, IsSupervisor
from nexofaena.services.reporte_service import ReporteService
from nexofaena.services.ml_service import MLService


class ReporteEppPorTurnoView(APIView):
    """
    Radiografía de consumo de EPP por trabajador y turno (pedido por el
    stakeholder Carlos Guerrero, RentaMaq): agrega lo que ya registra cada
    entrega, sin capturar nada nuevo. Solo Supervisor/Administrador pueden
    verlo; el RUT completo queda reservado al Administrador.
    """
    permission_classes = [IsSupervisor]

    def get(self, request):
        try:
            es_administrador = (
                hasattr(request.user, "rol") and request.user.rol.nombre == "Administrador"
            )

            producto = request.GET.get("producto")

            reporte = ReporteService.consumo_epp_por_turno(
                fecha_desde=request.GET.get("fecha_desde"),
                fecha_hasta=request.GET.get("fecha_hasta"),
                rut=request.GET.get("rut"),
                turno=request.GET.get("turno"),
                producto=producto,
                mostrar_rut_completo=es_administrador,
            )

            reporte["casos_revisar_historico"] = MLService.detectar_consumo_atipico_historico(
                fecha_desde=reporte["periodo"]["fecha_desde"],
                fecha_hasta=reporte["periodo"]["fecha_hasta"],
                rut=request.GET.get("rut"),
                producto=producto,
                mostrar_rut_completo=es_administrador,
            )

            return Response(reporte, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Error al generar el reporte de consumo por turno.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ReportePrestamosPendientesView(APIView):
    """
    "No saber quién tiene una radio que nunca devolvió" (Carlos Guerrero,
    RentaMaq). Es información operativa del día a día (bodega necesita saber
    a quién pedirle de vuelta un activo), por eso usa IsBodeguero y no queda
    reservado solo a Supervisor/Administrador como los reportes gerenciales.
    """
    permission_classes = [IsBodeguero]

    def get(self, request):
        try:
            es_administrador = (
                hasattr(request.user, "rol") and request.user.rol.nombre == "Administrador"
            )

            reporte = ReporteService.prestamos_pendientes(mostrar_rut_completo=es_administrador)

            return Response(reporte, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Error al generar el reporte de préstamos pendientes.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
