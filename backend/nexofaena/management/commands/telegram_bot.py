import json
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand

from nexofaena.models.telegram_bot import TelegramEstadoBot
from nexofaena.services import telegram_transporte
from nexofaena.services.notificacion_service import NotificationService

GET_UPDATES_URL = "https://api.telegram.org/bot{token}/getUpdates?timeout=25&offset={offset}"

# Telegram permite hasta 50s de long-poll; 25s deja margen y evita que un
# proxy/firewall intermedio corte la conexión por "inactividad".
TIMEOUT_LONG_POLL = 30
ESPERA_TRAS_ERROR_SEGUNDOS = 5
ESPERA_SIN_MENSAJES_SEGUNDOS = 2


class Command(BaseCommand):
    help = (
        "Corre el bot conversacional de Telegram por long-polling — pensado para "
        "correr en LAN/desarrollo sin URL pública (ver iniciar_bot_telegram.bat). "
        "En un despliegue en la nube con dominio propio, usa el webhook "
        "(ver views/telegram_webhook_views.py) en vez de este comando: ambos "
        "comparten la misma lógica de despacho en telegram_transporte.py, así "
        "que no hace falta mantener las dos formas corriendo a la vez."
    )

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN

        if not token:
            self.stderr.write(self.style.ERROR(
                "TELEGRAM_BOT_TOKEN no está configurado en .env — no hay nada que correr."
            ))
            return

        estado, _ = TelegramEstadoBot.objects.get_or_create(pk=1)

        if NotificationService.configurar_comandos_bot():
            self.stdout.write(self.style.SUCCESS("Menú de comandos registrado en Telegram."))
        else:
            self.stderr.write(self.style.WARNING(
                "No se pudo registrar el menú de comandos (no bloquea el resto del bot)."
            ))

        self.stdout.write(self.style.SUCCESS("Bot de Telegram escuchando (Ctrl+C para detener)..."))

        while True:
            try:
                actualizaciones = self._obtener_actualizaciones(token, estado.ultimo_update_id)
            except (urllib.error.URLError, urllib.error.HTTPError) as err:
                self.stderr.write(self.style.WARNING(f"Error consultando Telegram: {err}"))
                time.sleep(ESPERA_TRAS_ERROR_SEGUNDOS)
                continue

            for update in actualizaciones:
                estado.ultimo_update_id = update["update_id"] + 1
                estado.save(update_fields=["ultimo_update_id"])

                try:
                    telegram_transporte.procesar_update(update)
                except Exception as err:  # noqa: BLE001
                    # Un error procesando un mensaje puntual no debe tumbar
                    # el loop: se pierde esa respuesta, pero el bot sigue vivo.
                    self.stderr.write(self.style.WARNING(f"Error procesando update: {err}"))

            if not actualizaciones:
                time.sleep(ESPERA_SIN_MENSAJES_SEGUNDOS)

    def _obtener_actualizaciones(self, token, offset):
        url = GET_UPDATES_URL.format(token=token, offset=offset)

        with urllib.request.urlopen(url, timeout=TIMEOUT_LONG_POLL) as response:
            data = json.loads(response.read().decode("utf-8"))

        return data.get("result", [])
