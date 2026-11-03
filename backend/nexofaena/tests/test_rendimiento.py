from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.services.dashboard_service import CACHE_KEY_DASHBOARD, CACHE_KEY_RECALCULANDO, DashboardService
from nexofaena.tests.base import crear_bodega, crear_producto, crear_trabajador, crear_usuario


class _HiloRegistrado:
    """Reemplaza threading.Thread: registra que se lanzó, sin ejecutarlo."""
    lanzados = 0

    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        _HiloRegistrado.lanzados += 1


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False, DASHBOARD_RECALCULO_EN_SEGUNDO_PLANO=True)
@patch("nexofaena.services.dashboard_service.threading.Thread", _HiloRegistrado)
class CachePanelTests(TestCase):
    def setUp(self):
        cache.clear()
        _HiloRegistrado.lanzados = 0

    def test_la_primera_vez_calcula_y_despues_responde_del_cache(self):
        with patch.object(DashboardService, "_calcular_dashboard", return_value={"v": 1}) as calcular:
            self.assertEqual(DashboardService.obtener_dashboard(), {"v": 1})
            self.assertEqual(DashboardService.obtener_dashboard(), {"v": 1})

        calcular.assert_called_once()
        self.assertEqual(_HiloRegistrado.lanzados, 0)

    def test_un_cambio_no_hace_esperar_a_nadie(self):
        with patch.object(DashboardService, "_calcular_dashboard", return_value={"v": 1}):
            DashboardService.obtener_dashboard()

        DashboardService.invalidar_cache()

        with patch.object(DashboardService, "_calcular_dashboard", return_value={"v": 2}) as calcular:
            # Responde al instante con lo último calculado...
            self.assertEqual(DashboardService.obtener_dashboard(), {"v": 1})
            calcular.assert_not_called()
        # ...y el recálculo se lanzó en segundo plano.
        self.assertEqual(_HiloRegistrado.lanzados, 1)

    def test_no_lanza_dos_recalculos_a_la_vez(self):
        with patch.object(DashboardService, "_calcular_dashboard", return_value={"v": 1}):
            DashboardService.obtener_dashboard()
        DashboardService.invalidar_cache()

        DashboardService.obtener_dashboard()
        DashboardService.obtener_dashboard()

        self.assertEqual(_HiloRegistrado.lanzados, 1)
        self.assertTrue(cache.get(CACHE_KEY_RECALCULANDO))

    @override_settings(DASHBOARD_RECALCULO_EN_SEGUNDO_PLANO=False)
    def test_sin_segundo_plano_recalcula_en_la_misma_request(self):
        with patch.object(DashboardService, "_calcular_dashboard", return_value={"v": 1}):
            DashboardService.obtener_dashboard()
        DashboardService.invalidar_cache()

        with patch.object(DashboardService, "_calcular_dashboard", return_value={"v": 2}), \
                patch.object(DashboardService, "_calcular_ml_avanzado", return_value={}):
            DashboardService.obtener_dashboard()

        self.assertEqual(cache.get(CACHE_KEY_DASHBOARD)["datos"], {"v": 2})


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class ListasAcotadasTests(APITestCase):
    def setUp(self):
        self.usuario = crear_usuario(username="adm", rol_nombre="Administrador")
        self.client.force_authenticate(self.usuario)
        self.producto = crear_producto(crear_bodega(), stock=Decimal("100"))
        for i in range(8):
            MovimientoInventario.objects.create(
                usuario=self.usuario, bodega=self.producto.bodega, inventario=self.producto,
                tipo_movimiento="SALIDA", cantidad=Decimal("1"),
                stock_anterior=Decimal(100 - i), stock_actual=Decimal(99 - i),
            )

    def test_limite_devuelve_solo_los_mas_recientes(self):
        respuesta = self.client.get("/api/movimientos/?limite=3")

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(respuesta.data), 3)
        self.assertEqual(float(respuesta.data[0]["stock_actual"]), 92.0)  # el último registrado

    def test_sin_limite_devuelve_todo(self):
        self.assertEqual(len(self.client.get("/api/movimientos/").data), 8)

    def test_limite_no_afecta_ver_un_registro(self):
        movimiento = MovimientoInventario.objects.first()
        respuesta = self.client.get(f"/api/movimientos/{movimiento.id}/?limite=1")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_entregas_filtradas_por_mes(self):
        respuesta = self.client.get("/api/entregas-epp/?mes=1999-01&limite=10")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data, [])


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class DashboardOperativoTests(APITestCase):
    def test_cualquier_rol_ve_el_resumen_operativo(self):
        bodega = crear_bodega()
        crear_producto(bodega, nombre="Casco", stock=Decimal("2"), stock_minimo=Decimal("5"))
        crear_producto(bodega, nombre="Guantes", stock=Decimal("50"), stock_minimo=Decimal("5"))
        crear_trabajador()
        Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Casco bajo")
        self.client.force_authenticate(crear_usuario(username="op", rol_nombre="Operador"))

        respuesta = self.client.get("/api/dashboard/operativo/")

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data["productos_bajo_minimo"], 1)
        self.assertEqual(respuesta.data["trabajadores_activos"], 1)
        self.assertGreaterEqual(respuesta.data["alertas_abiertas"], 1)
        self.assertEqual(respuesta.data["radios_por_devolver"], 0)
        self.assertTrue(respuesta.data["alertas_recientes"])

    def test_sin_sesion_no_entra(self):
        self.assertEqual(self.client.get("/api/dashboard/operativo/").status_code, status.HTTP_401_UNAUTHORIZED)
