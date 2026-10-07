from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.tests.base import crear_bodega, crear_producto, crear_usuario


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class ListarAlertasTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(crear_usuario(username="bodeguero1", rol_nombre="Bodeguero"))
        self.creadas = 0

    def _crear_alertas(self, cantidad):
        for _ in range(cantidad):
            self.creadas += 1
            bodega = crear_bodega(nombre=f"Bodega {self.creadas}")
            producto = crear_producto(bodega, nombre=f"Producto {self.creadas}")
            Alerta.objects.create(
                bodega=bodega, inventario=producto,
                tipo_alerta=TipoAlerta.STOCK_BAJO, mensaje="Stock bajo",
            )

    def _queries_al_listar(self):
        with CaptureQueriesContext(connection) as contexto:
            respuesta = self.client.get("/api/alertas/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        return len(contexto.captured_queries)

    def test_cantidad_de_queries_no_crece_con_las_alertas(self):
        self._crear_alertas(2)
        queries_con_pocas = self._queries_al_listar()

        self._crear_alertas(8)
        queries_con_mas = self._queries_al_listar()

        self.assertEqual(queries_con_pocas, queries_con_mas)

    def test_incluye_nombres_de_bodega_y_producto(self):
        self._crear_alertas(1)

        respuesta = self.client.get("/api/alertas/")
        datos = respuesta.data["results"] if isinstance(respuesta.data, dict) else respuesta.data
        alerta = next(a for a in datos if a["tipo_alerta"] == TipoAlerta.STOCK_BAJO and a["mensaje"] == "Stock bajo")

        self.assertEqual(alerta["bodega_nombre"], "Bodega 1")
        self.assertEqual(alerta["inventario_nombre"], "Producto 1")
