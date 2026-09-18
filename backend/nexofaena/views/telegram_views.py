from django.conf import settings

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nexofaena.models.telegram_bot import TelegramVinculo
from nexofaena.services.telegram_bot_service import TelegramBotService


class TelegramEstadoVinculacionView(APIView):
    """Le dice al frontend si el usuario logueado ya vinculó su Telegram,
    para mostrar 'Vincular' o 'Ya vinculado' en vez de generar un código
    a ciegas."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vinculo = TelegramVinculo.objects.filter(usuario=request.user).first()

        return Response({
            "vinculado": vinculo is not None,
            "telegram_username": vinculo.telegram_username if vinculo else None,
            "bot_username": getattr(settings, "TELEGRAM_BOT_USERNAME", "") or None,
        })


class TelegramGenerarCodigoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        codigo = TelegramBotService.generar_codigo_vinculacion(request.user)
        bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")

        return Response(
            {
                "codigo": codigo.codigo,
                "expira_en": codigo.expira_en,
                "deep_link": f"https://t.me/{bot_username}?start={codigo.codigo}" if bot_username else None,
            },
            status=status.HTTP_201_CREATED,
        )
