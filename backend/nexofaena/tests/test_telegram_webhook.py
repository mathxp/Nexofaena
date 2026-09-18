import json
from unittest.mock import patch

from django.test import TestCase, override_settings

SECRETO = "secreto-de-prueba"


@override_settings(TELEGRAM_WEBHOOK_SECRET=SECRETO, TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class TelegramWebhookTests(TestCase):
    def _url(self, secreto=SECRETO):
        return f"/api/telegram/webhook/{secreto}/"

    def test_secreto_incorrecto_devuelve_404(self):
        respuesta = self.client.post(self._url("otro-secreto"), data="{}", content_type="application/json")
        self.assertEqual(respuesta.status_code, 404)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="")
    def test_sin_secreto_configurado_rechaza_todo(self):
        respuesta = self.client.post(self._url(), data="{}", content_type="application/json")
        self.assertEqual(respuesta.status_code, 404)

    def test_body_invalido_devuelve_400(self):
        respuesta = self.client.post(self._url(), data="no es json", content_type="application/json")
        self.assertEqual(respuesta.status_code, 400)

    def test_get_no_permitido(self):
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 405)

    @patch("nexofaena.services.telegram_transporte.TelegramBotService.procesar_mensaje")
    def test_update_valido_se_despacha_al_bot(self, mock_procesar):
        mock_procesar.return_value = ("hola", None)

        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "text": "/ayuda",
                "from": {"username": "alguien"},
            }
        }

        respuesta = self.client.post(self._url(), data=json.dumps(update), content_type="application/json")

        self.assertEqual(respuesta.status_code, 200)
        mock_procesar.assert_called_once_with(123, "/ayuda", "alguien")

    def test_update_de_grupo_se_ignora_pero_responde_200(self):
        update = {
            "message": {
                "chat": {"id": -999, "type": "supergroup"},
                "text": "/ayuda",
                "from": {"username": "alguien"},
            }
        }

        respuesta = self.client.post(self._url(), data=json.dumps(update), content_type="application/json")
        self.assertEqual(respuesta.status_code, 200)

    def test_error_al_procesar_no_devuelve_500(self):
        """Un error procesando un update no debe hacer que Telegram reintente
        en bucle: siempre responde 200, aunque el procesamiento falle."""
        with patch(
            "nexofaena.services.telegram_transporte.TelegramBotService.procesar_mensaje",
            side_effect=RuntimeError("boom"),
        ):
            update = {
                "message": {
                    "chat": {"id": 123, "type": "private"},
                    "text": "/ayuda",
                    "from": {"username": "alguien"},
                }
            }
            respuesta = self.client.post(self._url(), data=json.dumps(update), content_type="application/json")

        self.assertEqual(respuesta.status_code, 200)
