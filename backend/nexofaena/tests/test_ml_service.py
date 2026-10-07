from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from nexofaena.services.ml_service import MIN_PRODUCTOS_ABC, MIN_PRODUCTOS_TFIDF, MLService
from nexofaena.tests.base import crear_bodega, crear_producto

NOMBRES_CATALOGO = [
    "Casco de seguridad blanco",
    "Guantes de nitrilo",
    "Lentes de seguridad",
    "Zapato de seguridad",
    "Chaleco reflectante",
    "Protector auditivo",
]


def _nombres(respuesta):
    return [r["producto_nombre"] for r in respuesta["resultados"]]


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class BusquedaSemanticaTests(TestCase):
    def _crear_catalogo(self, cantidad):
        bodega = crear_bodega()
        for i, nombre in enumerate(NOMBRES_CATALOGO[:cantidad]):
            crear_producto(bodega, nombre=nombre, codigo=f"EPP-{i}")

    def test_frase_gerencial_con_plural_encuentra_el_producto(self):
        self._crear_catalogo(len(NOMBRES_CATALOGO))

        respuesta = MLService.buscar_kpi_por_texto("Resume el consumo de cascos del mes")

        self.assertTrue(respuesta["confiable"])
        self.assertEqual(_nombres(respuesta)[0], "Casco de seguridad blanco")
        self.assertIn("TF-IDF", respuesta["algoritmo"])

    def test_palabras_vacias_no_hacen_matchear_otros_productos(self):
        self._crear_catalogo(len(NOMBRES_CATALOGO))

        respuesta = MLService.buscar_kpi_por_texto("consumo de cascos")

        self.assertEqual(_nombres(respuesta), ["Casco de seguridad blanco"])

    def test_busca_por_codigo(self):
        self._crear_catalogo(len(NOMBRES_CATALOGO))

        respuesta = MLService.buscar_kpi_por_texto("EPP-1")

        self.assertEqual(_nombres(respuesta)[0], "Guantes de nitrilo")

    def test_catalogo_chico_usa_difflib_y_tolera_plurales(self):
        self._crear_catalogo(MIN_PRODUCTOS_TFIDF - 1)

        respuesta = MLService.buscar_kpi_por_texto("guante")

        self.assertIn("difflib", respuesta["algoritmo"])
        self.assertEqual(_nombres(respuesta), ["Guantes de nitrilo"])

    def test_consulta_sin_producto_pide_uno(self):
        self._crear_catalogo(len(NOMBRES_CATALOGO))

        respuesta = MLService.buscar_kpi_por_texto("consumo del mes")

        self.assertFalse(respuesta["confiable"])
        self.assertEqual(respuesta["resultados"], [])
        self.assertIn("qué producto", respuesta["motivo"])

    def test_sin_coincidencias_explica_el_motivo(self):
        self._crear_catalogo(len(NOMBRES_CATALOGO))

        respuesta = MLService.buscar_kpi_por_texto("xyzzy")

        self.assertFalse(respuesta["confiable"])
        self.assertIn("xyzzy", respuesta["motivo"])

    def test_consulta_vacia(self):
        respuesta = MLService.buscar_kpi_por_texto("   ")

        self.assertFalse(respuesta["confiable"])

    def test_ignora_productos_inactivos(self):
        self._crear_catalogo(len(NOMBRES_CATALOGO))
        crear_producto(crear_bodega(nombre="Otra"), nombre="Arnés de altura", codigo="ARN-1", estado=False)

        respuesta = MLService.buscar_kpi_por_texto("arnes")

        self.assertNotIn("Arnés de altura", _nombres(respuesta))


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class ClasificacionAbcTests(TestCase):
    def setUp(self):
        self.bodega = crear_bodega()

    def _producto(self, nombre, precio):
        producto = crear_producto(self.bodega, nombre=nombre)
        producto.precio_unitario = Decimal(precio)
        producto.save(update_fields=["precio_unitario"])
        return producto

    def _clasificar(self, rotacion_por_producto):
        with patch.object(MLService, "_rotacion_mensual_por_producto", return_value=rotacion_por_producto):
            respuesta = MLService.clasificacion_abc_dinamica()
        return respuesta, {i["producto_nombre"]: i["clase_abc"] for i in respuesta["items"]}

    def test_pareto_producto_dominante_es_clase_a(self):
        # Regresión: con el acumulado incluyendo al propio producto, el que
        # concentra >80% del valor quedaba como B y no había ninguna clase A.
        dominante = self._producto("Detector de gases", "900")
        medio = self._producto("Arnés", "80")
        menor = self._producto("Guantes", "20")

        respuesta, clases = self._clasificar({dominante.id: 1, medio.id: 1, menor.id: 1})

        self.assertIn("Pareto", respuesta["algoritmo"])
        self.assertEqual(clases, {"Detector de gases": "A", "Arnés": "B", "Guantes": "C"})

    def test_kmeans_separa_alto_valor_de_consumo_masivo(self):
        productos = {
            "Detector de gases": ("500000", 1),
            "Equipo autocontenido": ("480000", 2),
            "Arnés": ("60000", 10),
            "Línea de vida": ("55000", 12),
            "Guantes": ("2000", 400),
            "Tapones auditivos": ("500", 450),
        }
        self.assertGreaterEqual(len(productos), MIN_PRODUCTOS_ABC)
        rotacion = {self._producto(nombre, precio).id: rot for nombre, (precio, rot) in productos.items()}

        respuesta, clases = self._clasificar(rotacion)

        self.assertIn("K-Means", respuesta["algoritmo"])
        self.assertEqual(clases["Detector de gases"], "A")
        self.assertEqual(clases["Equipo autocontenido"], "A")
        self.assertEqual(clases["Guantes"], "C")
        self.assertEqual(clases["Tapones auditivos"], "C")
        self.assertEqual(clases["Arnés"], "B")
        self.assertEqual(respuesta["resumen"]["A"]["cantidad"], 2)

    def test_sin_precios_no_es_confiable(self):
        self._producto("Guantes", "0")

        respuesta, _ = self._clasificar({})

        self.assertFalse(respuesta["confiable"])
        self.assertEqual(respuesta["items"], [])
