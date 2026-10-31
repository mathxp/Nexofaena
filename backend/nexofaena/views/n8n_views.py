import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from nexofaena.services import n8n_service


class N8nResolverAlertaView(APIView):
    """
    n8n informa el resultado de una reposición (orden aprobada y enviada al
    proveedor, o rechazada). No usa el login de la app: n8n se autentica con
    la clave compartida N8N_TOKEN en el header X-NexoFaena-Token.

    Body JSON: {"estado": "aprobada" | "rechazada", "orden": "OC-0042",
                "aprobado_por": "Juan Pérez", "detalle": "texto libre"}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, alerta_id):
        if not settings.N8N_TOKEN:
            # Integración no configurada: no se confirma que la ruta exista.
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)

        token = request.headers.get("X-NexoFaena-Token", "")
        if not hmac.compare_digest(token, settings.N8N_TOKEN):
            return Response({"detail": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)

        estado = str(request.data.get("estado", "")).strip().lower()
        if estado not in n8n_service.ESTADOS_VALIDOS:
            return Response(
                {"detail": "estado debe ser 'aprobada' o 'rechazada'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        registro = n8n_service.registrar_resultado(
            alerta_id,
            estado,
            orden=str(request.data.get("orden", ""))[:50],
            detalle=str(request.data.get("detalle", ""))[:500],
            aprobado_por=str(request.data.get("aprobado_por", ""))[:100],
        )
        if registro is None:
            return Response({"detail": "Alerta de stock crítico no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"success": True, "registro_id": registro.id, "mensaje": registro.mensaje})
