from collections import defaultdict
from datetime import datetime
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from nexofaena.management.commands.seed_rentamaq import CANTIDAD_RADIOS, PEDIDO_PENDIENTE
from nexofaena.models.bodega import Bodega
from nexofaena.models.entrega import DetalleEntregaEPP, EntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.unidad_activo import UnidadActivo
from nexofaena.models.usuario import Usuario
from nexofaena.services.ml_service import MLService
from nexofaena.services.reporte_service import ReporteService
from nexofaena.tests.base import crear_bodega, crear_producto, crear_trabajador

# Mitad de mes y de jornada: los modelos miran "el mes en curso".
AHORA = datetime(2026, 10, 15, 13, 0, tzinfo=ZoneInfo("America/Santiago"))


def _sembrar(*args):
    call_command("seed_rentamaq", *args, stdout=StringIO())


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
@patch("django.utils.timezone.now", return_value=AHORA)
class SeedRentamaqTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with patch("django.utils.timezone.now", return_value=AHORA):
            _sembrar()

    def test_solo_dos_bodegas_y_las_radios(self, _now):
        self.assertEqual(set(Bodega.objects.values_list("codigo", flat=True)), {"BOD-CEN", "BOD-RES"})
        self.assertEqual(UnidadActivo.objects.count(), CANTIDAD_RADIOS)
        self.assertEqual(Trabajador.objects.count(), 40)

    def test_volumen_acotado(self, _now):
        # Suficiente para los modelos, sin inflar la base.
        self.assertTrue(800 < EntregaEPP.objects.count() < 2500, EntregaEPP.objects.count())
        self.assertLess(MovimientoInventario.objects.count(), 6000)

    def test_historial_termina_hoy_y_nunca_en_el_futuro(self, _now):
        ultima = MovimientoInventario.objects.order_by("-fecha").values_list("fecha", flat=True).first()
        self.assertLessEqual(ultima, AHORA)
        self.assertEqual(ultima.astimezone(AHORA.tzinfo).date(), AHORA.date())

    def test_cadena_de_stock_coherente_por_producto(self, _now):
        pasos = defaultdict(list)
        for mov in MovimientoInventario.objects.order_by("fecha", "id"):
            pasos[mov.inventario_id].append((mov.stock_anterior, mov.stock_actual))
            if mov.inventario_destino_id:
                pasos[mov.inventario_destino_id].append((mov.stock_anterior_destino, mov.stock_actual_destino))

        for inventario in Inventario.objects.all():
            cadena = pasos.get(inventario.id, [])
            for (_, despues), (antes, _) in zip(cadena, cadena[1:]):
                self.assertEqual(despues, antes, inventario.nombre)
            if cadena:
                self.assertEqual(cadena[-1][1], inventario.stock_actual, inventario.nombre)
            self.assertGreaterEqual(inventario.stock_actual, 0)

    def test_radios_coherentes_con_sus_prestamos(self, _now):
        pendientes = DetalleEntregaEPP.objects.filter(unidad_activo__isnull=False, devuelto=False)
        entregadas = UnidadActivo.objects.filter(estado="ENTREGADA")
        self.assertEqual(set(pendientes.values_list("unidad_activo_id", flat=True)),
                         set(entregadas.values_list("id", flat=True)))
        self.assertGreater(ReporteService.prestamos_pendientes()["total_items"], 0)

    def test_el_panel_tiene_escenarios_reales(self, _now):
        analitica = MLService.analitica_stock()

        urgentes = {r["producto_nombre"] for r in analitica["recomendaciones_reposicion"] if r["probabilidad_quiebre"] >= 70}
        for nombre in PEDIDO_PENDIENTE:
            self.assertIn(nombre, urgentes)

        anomalias = MLService.detectar_anomalias()
        self.assertTrue(1 <= len(anomalias) <= 4, [a["trabajador_nombre"] for a in anomalias])

        # Ni la reserva ni los equipos devolutivos cuentan como "dinero detenido sin consumo".
        for item in analitica["capital_inmovilizado"]["items"]:
            producto = Inventario.objects.select_related("bodega").get(id=item["inventario_id"])
            self.assertEqual(producto.bodega.tipo, "CENTRAL")
            self.assertFalse(producto.es_devolutivo)

    def test_un_producto_por_nombre_y_bodega(self, _now):
        from django.db.models import Count

        repetidos = (
            Inventario.objects.values("bodega__codigo", "nombre")
            .annotate(n=Count("id")).filter(n__gt=1)
        )
        self.assertFalse(repetidos.exists(), list(repetidos))
        self.assertLessEqual(Inventario.objects.filter(nombre="Zapato de seguridad").count(), 2)
        # La reserva solo guarda respaldo: tiene bastante menos que la central.
        self.assertLess(
            Inventario.objects.filter(bodega__codigo="BOD-RES").count(),
            Inventario.objects.filter(bodega__codigo="BOD-CEN").count() / 2,
        )

    def test_la_talla_se_anota_en_cada_entrega(self, _now):
        tallas = set(
            DetalleEntregaEPP.objects.filter(inventario__nombre="Zapato de seguridad")
            .values_list("talla", flat=True)
        )
        if tallas:  # se entregan solo cada varios meses: puede no haber en 4 meses
            self.assertTrue(tallas <= {str(t) for t in range(38, 47)}, tallas)

    def test_personal_de_bodega_no_puede_iniciar_sesion(self, _now):
        for usuario in Usuario.objects.filter(username__in=["bodeguero1", "encargado1"]):
            self.assertFalse(usuario.is_active)
            self.assertFalse(usuario.has_usable_password())
            self.assertFalse(usuario.is_superuser)

    def test_sin_reset_no_duplica(self, _now):
        entregas = EntregaEPP.objects.count()
        _sembrar()
        self.assertEqual(EntregaEPP.objects.count(), entregas)


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
@patch("django.utils.timezone.now", return_value=AHORA)
class SeedResetTests(TestCase):
    def test_reset_exige_confirmar_respaldo(self, _now):
        with self.assertRaises(CommandError):
            _sembrar("--reset")

    def test_reset_deja_solo_las_dos_bodegas_del_panol(self, _now):
        extra = crear_bodega(nombre="Faena Demo")
        crear_producto(extra, nombre="Casco demo", codigo="DEMO-CASCO")
        crear_trabajador(rut="21900001-0")

        _sembrar("--reset", "--confirmo-respaldo")

        self.assertFalse(Bodega.objects.filter(nombre="Faena Demo").exists())
        self.assertFalse(Inventario.objects.filter(codigo="DEMO-CASCO").exists())
        self.assertEqual(Bodega.objects.count(), 2)
