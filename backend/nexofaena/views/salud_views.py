from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class SaludView(APIView):
    """Responde "ok" sin tocar la base de datos.

    El kiosco lo llama cada pocos minutos mientras está abierto: en el plan
    gratis de Render el servidor se duerme tras 15 minutos sin tráfico, y la
    primera petición después tardaba cerca de un minuto (el trabajador quedaba
    esperando al ser reconocido). También sirve para un monitor externo.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"estado": "ok"})
