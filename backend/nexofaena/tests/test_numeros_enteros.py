"""Todo el sistema trabaja con cantidades enteras: se guardan, se muestran y
se aceptan solo números enteros."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from nexofaena.services.entrega_service import EntregaService
from nexofaena.services.numeros import cantidad_entera, redondear
from nexofaena.tests.base import crear_bodega, crear_producto, crear_trabajador, crear_usuario


class NumerosTests(SimpleTestCase):
    def test_redondear_como_a_mano(self):
        self.assertEqual(redondear(2.5), 3)
        self.assertEqual(redondear(0.5), 1)
        self.assertEqual(redondear(2.4), 2)
        self.assertEqual(redondear(Decimal("14.00")), 14)
        self.assertEqual(redondear(None), 0)

    def test_cantidad_entera_acepta_enteros_escritos_de_varias_formas(self):
        for valor in (3, "3", "3.00", " 3 ", Decimal("3.0")):
            self.assertEqual(cantidad_entera(valor), Decimal("3"))

    def test_cantidad_entera_rechaza_decimales_y_texto(self):
        for valor in ("1.5", 1.5, "2,5", "abc", "", None, "NaN", "Infinity"):
            with self.assertRaises(ValueError, msg=repr(valor)):
                cantidad_entera(valor)


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class CantidadesEnterasEnLaApiTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario(rol_nombre="Administrador", username="admin_enteros")
        self.bodega = crear_bodega()
        self.producto = crear_producto(self.bodega, stock=Decimal("10"))
        self.client = APIClient()
        self.client.force_authenticate(self.usuario)

    def test_el_inventario_se_entrega_sin_decimales(self):
        respuesta = self.client.get(f"/api/inventario/{self.producto.id}/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["stock_actual"], "10")
        self.assertEqual(respuesta.data["precio_unitario"], "1000")

    def test_el_inventario_rechaza_un_minimo_con_decimales(self):
        respuesta = self.client.patch(
            f"/api/inventario/{self.producto.id}/", {"stock_minimo": "1.5"}, format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("entero", str(respuesta.data["stock_minimo"]))

    def test_un_movimiento_con_decimales_o_texto_se_rechaza_sin_tocar_el_stock(self):
        for cantidad in ("1.5", "abc"):
            respuesta = self.client.post("/api/movimientos/", {
                "inventario": self.producto.id, "bodega": self.bodega.id,
                "tipo_movimiento": "INGRESO", "cantidad": cantidad,
            }, format="json")
            self.assertEqual(respuesta.status_code, 400, cantidad)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, Decimal("10"))

    def test_un_movimiento_entero_suma_el_stock(self):
        respuesta = self.client.post("/api/movimientos/", {
            "inventario": self.producto.id, "bodega": self.bodega.id,
            "tipo_movimiento": "INGRESO", "cantidad": "5",
        }, format="json")

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, Decimal("15"))

    def test_una_entrega_con_decimales_se_rechaza(self):
        with self.assertRaises(ValidationError):
            EntregaService.crear_entrega(
                trabajador_id=crear_trabajador().id,
                usuario_id=self.usuario.id,
                bodega_id=self.bodega.id,
                detalles=[{"inventario": self.producto.id, "cantidad": "1.5"}],
            )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, Decimal("10"))
