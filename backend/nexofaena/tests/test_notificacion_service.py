from django.test import TestCase

from nexofaena.services.notificacion_service import escapar_html


class EscaparHtmlTests(TestCase):
    """
    Cubre exactamente el bug que rompió las notificaciones de Telegram en
    producción: con parse_mode=HTML, un solo "&", "<" o ">" sin escapar en
    un nombre de producto/mensaje generado dinámicamente hace que Telegram
    rechace el envío completo.
    """

    def test_escapa_ampersand(self):
        self.assertEqual(escapar_html("Cascos & guantes"), "Cascos &amp; guantes")

    def test_escapa_angulos(self):
        self.assertEqual(escapar_html("<script>"), "&lt;script&gt;")

    def test_texto_normal_no_cambia(self):
        self.assertEqual(escapar_html("Casco de seguridad"), "Casco de seguridad")

    def test_convierte_no_strings(self):
        self.assertEqual(escapar_html(142), "142")
