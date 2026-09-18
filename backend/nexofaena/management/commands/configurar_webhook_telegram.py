import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from nexofaena.services.notificacion_service import NotificationService


class Command(BaseCommand):
    help = (
        "Registra (o quita, con --quitar) el webhook de Telegram, apuntando al "
        "dominio público donde está desplegado el backend. Se corre UNA vez "
        "después de cada despliegue con una URL nueva — no hace falta dejarlo "
        "corriendo. Requiere TELEGRAM_WEBHOOK_SECRET configurado en el entorno."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "url_base", nargs="?",
            help="URL pública del backend, sin barra final. Ej: https://nexofaena-backend.onrender.com",
        )
        parser.add_argument("--quitar", action="store_true", help="Quita el webhook (vuelve a modo sin bot activo).")

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN no está configurado.")

        if options["quitar"]:
            self._llamar("deleteWebhook", token, {})
            self.stdout.write(self.style.SUCCESS("Webhook de Telegram eliminado."))
            return

        url_base = options["url_base"]
        if not url_base:
            raise CommandError("Falta la URL base. Ej: configurar_webhook_telegram https://tu-app.onrender.com")

        if not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError(
                "TELEGRAM_WEBHOOK_SECRET no está configurado en el entorno. Genera uno "
                "(ej. con `python -c \"import secrets;print(secrets.token_urlsafe(32))\"`) "
                "y agrégalo antes de correr este comando."
            )

        webhook_url = f"{url_base.rstrip('/')}/api/telegram/webhook/{settings.TELEGRAM_WEBHOOK_SECRET}/"

        resultado = self._llamar("setWebhook", token, {"url": webhook_url, "drop_pending_updates": True})

        if resultado.get("ok"):
            self.stdout.write(self.style.SUCCESS(f"Webhook registrado: {webhook_url}"))
        else:
            raise CommandError(f"Telegram rechazó el webhook: {resultado}")

        if NotificationService.configurar_comandos_bot():
            self.stdout.write(self.style.SUCCESS("Menú de comandos registrado en Telegram."))

    def _llamar(self, metodo, token, payload):
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/{metodo}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            detalle = err.read().decode("utf-8", errors="replace")
            raise CommandError(f"Error de Telegram ({err.code}): {detalle}")
        except urllib.error.URLError as err:
            raise CommandError(f"No se pudo contactar a Telegram: {err}")
