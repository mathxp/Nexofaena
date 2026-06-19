from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response

from nexofaena.models.alerta import Alerta
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.inventario import Inventario
from nexofaena.models.entrega_epp import EntregaEPP

from nexofaena.serializers.alerta_serializer import AlertaSerializer

# 1. ViewSet normal para leer o marcar alertas como leídas
class AlertaViewSet(viewsets.ModelViewSet):
    queryset = Alerta.objects.all().order_by('-fecha_alerta') # Ordenamos de la más nueva a la más vieja
    serializer_class = AlertaSerializer

# 2. Vista especial para el Dashboard (Indicadores)
class DashboardResumenView(APIView):
    def get(self, request):
        # Calculamos los datos clave de la faena
        total_trabajadores = Trabajador.objects.filter(activo=True).count()
        total_productos = Inventario.objects.filter(estado=True).count()
        entregas_pendientes = EntregaEPP.objects.filter(estado='PENDIENTE').count()
        alertas_no_leidas = Alerta.objects.filter(leida=False).count()

        # Armamos la respuesta JSON que consumirá React
        data = {
            "indicadores": {
                "trabajadores_activos": total_trabajadores,
                "productos_en_inventario": total_productos,
                "entregas_pendientes_firma": entregas_pendientes,
                "alertas_nuevas": alertas_no_leidas
            }
        }
        
        return Response(data)