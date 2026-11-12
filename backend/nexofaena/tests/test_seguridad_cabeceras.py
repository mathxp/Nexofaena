"""Hallazgos del reconocimiento de seguridad: que no vuelvan a aparecer."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from nexofaena.tests.base import crear_usuario

RUTA_N8N = "/api/integraciones/n8n/alertas/1/resolver/"


class SeguridadCabecerasTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_options_no_revela_como_se_autentica_un_endpoint(self):
        respuesta = self.client.options(RUTA_N8N)

        self.assertNotEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertNotIn("X-NexoFaena-Token", contenido)
        self.assertNotIn("N8N_TOKEN", contenido)

    @override_settings(CORS_ALLOWED_ORIGINS=["https://nexofaena.pages.dev"])
    def test_el_preflight_cors_del_frontend_sigue_funcionando(self):
        respuesta = self.client.options(
            "/api/inventario/",
            HTTP_ORIGIN="https://nexofaena.pages.dev",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Access-Control-Allow-Origin"], "https://nexofaena.pages.dev")

    def test_toda_respuesta_lleva_csp_y_anti_iframe(self):
        respuesta = self.client.get("/api/inventario/")

        self.assertIn("frame-ancestors 'none'", respuesta["Content-Security-Policy"])
        self.assertIn("object-src 'none'", respuesta["Content-Security-Policy"])
        self.assertEqual(respuesta["X-Frame-Options"], "DENY")
        self.assertEqual(respuesta["X-Content-Type-Options"], "nosniff")

    @override_settings(SECURE_HSTS_SECONDS=31536000, SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
                       SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_hsts_detras_del_proxy_https_de_render(self):
        respuesta = self.client.get("/api/inventario/", HTTP_X_FORWARDED_PROTO="https")

        self.assertEqual(respuesta["Strict-Transport-Security"], "max-age=31536000; includeSubDomains")

    def test_esquema_y_documentacion_no_son_publicos(self):
        for ruta in ("/api/schema/", "/api/docs/"):
            self.assertIn(self.client.get(ruta).status_code, (401, 403), ruta)

    def test_un_usuario_normal_tampoco_ve_el_esquema(self):
        self.client.force_authenticate(crear_usuario(username="bodeguero_schema"))
        self.assertEqual(self.client.get("/api/schema/").status_code, 403)

    def test_un_administrador_si_ve_la_documentacion(self):
        admin = crear_usuario(username="admin_schema", rol_nombre="Administrador", is_staff=True)
        self.client.force_authenticate(admin)

        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
        docs = self.client.get("/api/docs/")
        self.assertEqual(docs.status_code, 200)
        # La CSP bloquea scripts inline: Swagger debe cargar su script aparte.
        self.assertNotIn("<script>", docs.content.decode())


class SaludTests(TestCase):
    def test_salud_responde_sin_login_y_sin_datos_internos(self):
        respuesta = APIClient().get("/api/salud/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "ok"})
