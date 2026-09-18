from unittest.mock import patch

from django.test import TestCase

from nexofaena.models.alerta import Alerta, TipoAlerta


class AlertaSignalTests(TestCase):
    """
    Verifica que crear una Alerta de tipo notificable dispare el bot de
    Telegram (vía la señal post_save en signals.py) sin tocar la red real:
    se reemplaza NotificationService.enviar_telegram por un mock.
    """

    @patch("nexofaena.services.notificacion_service.NotificationService.enviar_telegram")
    def test_alerta_critica_dispara_notificacion(self, mock_enviar):
        Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Stock crítico de prueba")

        mock_enviar.assert_called_once()
        texto_enviado = mock_enviar.call_args.args[0]
        self.assertIn("Stock crítico de prueba", texto_enviado)

    @patch("nexofaena.services.notificacion_service.NotificationService.enviar_telegram")
    def test_alerta_no_critica_no_dispara_notificacion(self, mock_enviar):
        Alerta.objects.create(tipo_alerta=TipoAlerta.MANTENIMIENTO, mensaje="Mantención de prueba")

        mock_enviar.assert_not_called()

    @patch("nexofaena.services.notificacion_service.NotificationService.enviar_telegram")
    def test_actualizar_alerta_existente_no_reenvia(self, mock_enviar):
        alerta = Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Original")
        mock_enviar.reset_mock()

        alerta.leida = True
        alerta.save(update_fields=["leida"])

        mock_enviar.assert_not_called()
