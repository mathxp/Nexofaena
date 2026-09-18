import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from nexofaena.services import telegram_transporte

logger = logging.getLogger("nexofaena")


@csrf_exempt
@require_POST
def telegram_webhook(request, secreto):
    """
    Punto de entrada del bot cuando corre en la nube (Render, etc.) en vez
    de long-polling: Telegram le hace POST a esta URL cada vez que hay un
    mensaje nuevo. No necesita un worker aparte corriendo 24/7 (que en la
    mayoría de los free tier cuesta aparte) — es solo otro endpoint del
    mismo servicio web.

    El secreto va en la URL (no en query string, para que no quede en
    logs de acceso típicos) y debe calzar con TELEGRAM_WEBHOOK_SECRET:
    sin él, cualquiera podría mandar "updates" falsos haciéndose pasar
    por Telegram. Se registra una sola vez con
    `python manage.py configurar_webhook_telegram <url-base>`.
    """
    if not settings.TELEGRAM_WEBHOOK_SECRET or secreto != settings.TELEGRAM_WEBHOOK_SECRET:
        # 404 en vez de 403: no le confirma a quien esté probando URLs al
        # azar que el path existe pero el secreto está mal.
        return JsonResponse({"ok": False}, status=404)

    try:
        update = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False}, status=400)

    try:
        telegram_transporte.procesar_update(update)
    except Exception as err:  # noqa: BLE001
        # Un error procesando un update puntual nunca debe devolver 500:
        # Telegram reintentaría el mismo update en bucle. Se loguea y se
        # responde 200 igual — se pierde esa respuesta puntual, no el bot.
        logger.warning("Error procesando update de Telegram (webhook): %s", err)

    return JsonResponse({"ok": True})
