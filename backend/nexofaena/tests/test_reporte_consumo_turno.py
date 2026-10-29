from datetime import datetime
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase, override_settings

from nexofaena.services.reporte_service import ReporteService

AHORA = datetime(2026, 10, 15, 13, 0, tzinfo=ZoneInfo("America/Santiago"))


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
@patch("django.utils.timezone.now", return_value=AHORA)
class ReporteConsumoTurnoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with patch("django.utils.timezone.now", return_value=AHORA):
            call_command("seed_rentamaq", stdout=StringIO())

    def _reporte(self, **filtros):
        return ReporteService.consumo_epp_por_turno(fecha_desde="2026-09-15", fecha_hasta="2026-10-15", **filtros)

    def test_una_fila_por_trabajador(self, _now):
        reporte = self._reporte()
        ids = [r["trabajador_id"] for r in reporte["resumen_por_trabajador"]]

        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(reporte["resumen_general"]["trabajadores_evaluados"], len(ids))

    def test_las_radios_no_cuentan_como_consumo(self, _now):
        for fila in self._reporte()["resumen_por_trabajador"]:
            nombres = {p["producto_nombre"] for p in fila["desglose_por_producto"]}
            self.assertFalse(any("Radio" in n or "radio" in n for n in nombres), nombres)

    def test_pocos_casos_a_revisar(self, _now):
        reporte = self._reporte()
        revisar = [r for r in reporte["resumen_por_trabajador"] if r["estado_revision"] == "revisar"]

        self.assertTrue(1 <= len(revisar) <= 4, [r["trabajador_nombre"] for r in revisar])
        self.assertEqual(reporte["resumen_general"]["a_revisar"], len(revisar))
        # Los casos a revisar van primero.
        self.assertEqual(reporte["resumen_por_trabajador"][0]["estado_revision"], "revisar")

    def test_los_totales_cuadran(self, _now):
        reporte = self._reporte()
        filas = reporte["resumen_por_trabajador"]

        self.assertAlmostEqual(sum(t["unidades"] for t in reporte["por_turno"]),
                               reporte["resumen_general"]["total_unidades"], places=0)
        for fila in filas:
            self.assertAlmostEqual(sum(fila["unidades_por_turno"].values()), fila["total_unidades"], places=0)
            self.assertAlmostEqual(sum(p["cantidad"] for p in fila["desglose_por_producto"]), fila["total_unidades"], places=0)

    def test_filtrar_por_producto_cuenta_solo_esas_visitas(self, _now):
        general = {r["trabajador_id"]: r for r in self._reporte()["resumen_por_trabajador"]}
        filtrado = self._reporte(producto="guantes")["resumen_por_trabajador"]

        self.assertTrue(filtrado)
        for fila in filtrado:
            self.assertLessEqual(fila["num_visitas"], general[fila["trabajador_id"]]["num_visitas"])
            self.assertTrue(all("Guantes" in p["producto_nombre"] for p in fila["desglose_por_producto"]))
            self.assertAlmostEqual(fila["unidades_por_visita"], round(fila["total_unidades"] / fila["num_visitas"], 1))

    def test_filtrar_por_turno(self, _now):
        reporte = self._reporte(turno="noche")
        self.assertTrue(all(t["turno"] == "noche" for t in reporte["por_turno"]))
        for fila in reporte["resumen_por_trabajador"]:
            self.assertEqual(fila["unidades_por_turno"]["dia"], 0)
