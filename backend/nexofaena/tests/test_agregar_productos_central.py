from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from nexofaena.management.commands.agregar_productos_central import PRODUCTOS
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.tests.base import crear_bodega, crear_producto, crear_usuario


def correr(*args):
    salida = StringIO()
    call_command("agregar_productos_central", *args, stdout=salida)
    return salida.getvalue()


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class AgregarProductosCentralTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario(username="admin_carga", rol_nombre="Administrador")
        self.central = crear_bodega("Bodega Central")
        # Ya existe con stock sano: no debe duplicarse ni tocarse.
        self.casco = crear_producto(self.central, nombre="Casco de seguridad", codigo="RM-0015",
                                    stock=Decimal("26"), stock_minimo=Decimal("8"), stock_maximo=Decimal("40"))
        # Ya existe pero agotado: debe reponerse.
        self.lentes = crear_producto(self.central, nombre="Lentes de seguridad oscuros", codigo="RM-0020",
                                     stock=Decimal("0"), stock_minimo=Decimal("5"), stock_maximo=Decimal("30"))

    def test_sin_aplicar_no_guarda_nada(self):
        salida = correr()

        self.assertIn("solo revisar", salida)
        self.assertEqual(Inventario.objects.count(), 2)
        self.assertFalse(MovimientoInventario.objects.exists())
        self.lentes.refresh_from_db()
        self.assertEqual(self.lentes.stock_actual, Decimal("0"))

    def test_aplicar_crea_lo_que_falta_y_repone_lo_agotado(self):
        correr("--aplicar")

        for nombre, *_ in PRODUCTOS:
            self.assertEqual(Inventario.objects.filter(bodega=self.central, nombre=nombre).count(), 1, nombre)
            producto = Inventario.objects.get(bodega=self.central, nombre=nombre)
            self.assertGreaterEqual(producto.stock_actual, producto.stock_minimo, nombre)
            self.assertGreater(producto.stock_actual, 0, nombre)

        self.casco.refresh_from_db()
        self.assertEqual(self.casco.stock_actual, Decimal("26"), "no se toca un stock sano")
        self.assertFalse(MovimientoInventario.objects.filter(inventario=self.casco).exists())

        self.lentes.refresh_from_db()
        self.assertEqual(self.lentes.stock_actual, Decimal("30"))
        ingreso = MovimientoInventario.objects.get(inventario=self.lentes)
        self.assertEqual((ingreso.tipo_movimiento, ingreso.cantidad, ingreso.usuario), ("INGRESO", Decimal("30"), self.admin))

        # Toman los siguientes códigos RM libres, en orden.
        self.assertEqual(Inventario.objects.get(nombre="Plumón permanente").codigo, "RM-0021")
        self.assertEqual(Inventario.objects.get(nombre="Linterna para casco").codigo, "RM-0022")

    def test_correrlo_dos_veces_no_duplica_nada(self):
        correr("--aplicar")
        productos, movimientos = Inventario.objects.count(), MovimientoInventario.objects.count()

        salida = correr("--aplicar")

        self.assertEqual(Inventario.objects.count(), productos)
        self.assertEqual(MovimientoInventario.objects.count(), movimientos)
        self.assertIn("0 cambio(s)", salida)
