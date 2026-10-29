from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase, override_settings

from nexofaena.management.commands.generar_demo_dashboard import (
    CODIGO_BODEGA, PRODUCTOS_DEMO, RUTS_DEMO, USERNAME_DEMO,
)
from nexofaena.models.bodega import Bodega
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.usuario import Usuario
from nexofaena.services.ml_service import MLService

# Mitad de mes y de jornada: el comando y los modelos miran "el mes en
# curso" y "hasta la hora actual", así que el test no puede depender de que
# se corra un día 1 a las 6 AM.
AHORA = datetime(2026, 10, 15, 13, 0, tzinfo=ZoneInfo("America/Santiago"))


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
@patch("django.utils.timezone.now", return_value=AHORA)
class GenerarDemoDashboardTests(TestCase):
    def _generar(self):
        call_command("generar_demo_dashboard", stdout=StringIO())

    def test_stock_final_y_movimientos_son_coherentes(self, _now):
        self._generar()

        for codigo, _, _, stock_final, *_ in PRODUCTOS_DEMO:
            producto = Inventario.objects.get(codigo=codigo)
            self.assertEqual(float(producto.stock_actual), stock_final)

            movimientos = list(MovimientoInventario.objects.filter(inventario=producto).order_by("fecha", "id"))
            self.assertTrue(movimientos, codigo)
            for mov in movimientos:
                signo = -1 if mov.tipo_movimiento == "SALIDA" else 1
                self.assertEqual(mov.stock_anterior + signo * mov.cantidad, mov.stock_actual, (codigo, mov.id))
                self.assertGreaterEqual(mov.stock_actual, 0)
            # El último movimiento deja exactamente el stock de hoy.
            self.assertEqual(movimientos[-1].stock_actual, producto.stock_actual)

    def test_fechas_dentro_de_las_12_semanas_y_nunca_en_el_futuro(self, _now):
        self._generar()

        fechas = MovimientoInventario.objects.values_list("fecha", flat=True)
        self.assertTrue(all(AHORA - timedelta(days=85) <= f <= AHORA for f in fechas))

    def test_el_panel_muestra_los_escenarios_de_la_demo(self, _now):
        self._generar()

        analitica = MLService.analitica_stock()
        recomendados = {r["producto_nombre"]: r["probabilidad_quiebre"] for r in analitica["recomendaciones_reposicion"]}
        for urgente in ("Casco de seguridad", "Guantes de nitrilo (par)", "Filtro respirador medio rostro"):
            self.assertIn(urgente, recomendados)
            self.assertGreaterEqual(recomendados[urgente], 70, urgente)

        exceso = {c["producto_nombre"] for c in analitica["capital_inmovilizado"]["items"]}
        self.assertIn("Arnés de altura", exceso)

        anomalos = {a["trabajador_nombre"] for a in MLService.detectar_anomalias()}
        self.assertEqual(anomalos, {"Pedro Rojas", "Matías Fuentes"})

    def test_regenerar_no_duplica(self, _now):
        self._generar()
        primera = MovimientoInventario.objects.count()

        self._generar()

        self.assertEqual(Bodega.objects.filter(codigo=CODIGO_BODEGA).count(), 1)
        self.assertEqual(Trabajador.objects.filter(rut__in=RUTS_DEMO).count(), len(RUTS_DEMO))
        self.assertEqual(MovimientoInventario.objects.count(), primera)

    def test_borrar_elimina_todo_lo_de_la_demo(self, _now):
        self._generar()

        call_command("generar_demo_dashboard", "--borrar", stdout=StringIO())

        self.assertFalse(Bodega.objects.filter(codigo=CODIGO_BODEGA).exists())
        self.assertFalse(Inventario.objects.filter(codigo__startswith="DEMO-").exists())
        self.assertFalse(Trabajador.objects.filter(rut__in=RUTS_DEMO).exists())
        self.assertFalse(Usuario.objects.filter(username=USERNAME_DEMO).exists())
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_usuario_demo_no_puede_iniciar_sesion(self, _now):
        self._generar()

        usuario = Usuario.objects.get(username=USERNAME_DEMO)
        self.assertFalse(usuario.is_active)
        self.assertFalse(usuario.has_usable_password())
