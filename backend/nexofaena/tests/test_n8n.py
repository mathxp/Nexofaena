from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.services.alerta_service import AlertaService
from nexofaena.tests.base import crear_bodega, crear_producto

URL_N8N = "https://n8n.ejemplo.cl/webhook/nexofaena-stock-critico"
TOKEN = "clave-de-prueba"


class _HiloInmediato:
    """Reemplaza threading.Thread: ejecuta el envío en el acto para poder verificarlo."""

    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False, N8N_WEBHOOK_URL=URL_N8N, N8N_TOKEN=TOKEN)
@patch("nexofaena.services.n8n_service.threading.Thread", _HiloInmediato)
@patch("nexofaena.services.n8n_service._enviar", return_value=True)
class AvisoStockCriticoTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(
            crear_bodega(), nombre="Guantes de nitrilo", stock=Decimal("50"), stock_minimo=Decimal("20"),
        )
        self.producto.stock_maximo = Decimal("200")
        self.producto.precio_unitario = Decimal("1490")
        self.producto.save()

    def _bajar_stock_a(self, cantidad):
        self.producto.stock_actual = Decimal(cantidad)
        self.producto.save(update_fields=["stock_actual"])
        with self.captureOnCommitCallbacks(execute=True):
            return AlertaService.verificar_stock_producto(self.producto)

    def test_stock_critico_avisa_a_n8n_con_lo_necesario_para_cotizar(self, enviar):
        alerta = self._bajar_stock_a(8)

        enviar.assert_called_once()
        aviso = enviar.call_args.args[0]
        self.assertEqual(aviso["evento"], "stock_critico")
        self.assertEqual(aviso["alerta_id"], alerta.id)
        self.assertEqual(aviso["producto"]["nombre"], "Guantes de nitrilo")
        self.assertEqual(aviso["stock"], {"actual": 8.0, "minimo": 20.0, "maximo": 200.0})
        self.assertEqual(aviso["reposicion"]["cantidad_sugerida"], 192)  # hasta el máximo
        self.assertEqual(aviso["reposicion"]["costo_estimado_clp"], 192 * 1490)

    def test_avisa_una_sola_vez_mientras_la_alerta_siga_abierta(self, enviar):
        self._bajar_stock_a(8)
        self._bajar_stock_a(5)

        enviar.assert_called_once()

    def test_stock_justo_en_el_minimo_no_avisa(self, enviar):
        self._bajar_stock_a(20)  # STOCK_BAJO, no crítico
        enviar.assert_not_called()

    @override_settings(N8N_WEBHOOK_URL="")
    def test_sin_url_configurada_no_envia_nada(self, enviar):
        self._bajar_stock_a(8)
        enviar.assert_not_called()


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False, N8N_TOKEN=TOKEN, N8N_WEBHOOK_URL="")
class ResolverAlertaTests(APITestCase):
    def setUp(self):
        self.producto = crear_producto(crear_bodega(), nombre="Casco de seguridad")
        self.alerta = Alerta.objects.create(
            inventario=self.producto, bodega=self.producto.bodega,
            tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Casco en stock crítico",
        )

    def _resolver(self, datos, token=TOKEN, alerta_id=None):
        return self.client.post(
            f"/api/integraciones/n8n/alertas/{alerta_id or self.alerta.id}/resolver/",
            datos, format="json", HTTP_X_NEXOFAENA_TOKEN=token,
        )

    def test_orden_aprobada_cierra_la_alerta_y_queda_en_el_historial(self):
        respuesta = self._resolver({"estado": "aprobada", "orden": "OC-0042", "aprobado_por": "Ana Soto"})

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.leida)
        registro = Alerta.objects.get(tipo_alerta=TipoAlerta.SISTEMA)
        self.assertIn("OC-0042", registro.mensaje)
        self.assertIn("Ana Soto", registro.mensaje)

    def test_rechazada_deja_la_alerta_abierta(self):
        respuesta = self._resolver({"estado": "rechazada"})

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.leida)
        self.assertIn("rechazada", Alerta.objects.get(tipo_alerta=TipoAlerta.SISTEMA).mensaje)

    def test_token_incorrecto(self):
        respuesta = self._resolver({"estado": "aprobada"}, token="otro")
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_estado_invalido(self):
        respuesta = self._resolver({"estado": "quizas"})
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_alerta_inexistente(self):
        respuesta = self._resolver({"estado": "aprobada"}, alerta_id=999999)
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(N8N_TOKEN="")
    def test_sin_token_configurado_la_ruta_no_existe(self):
        respuesta = self._resolver({"estado": "aprobada"}, token="")
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)
