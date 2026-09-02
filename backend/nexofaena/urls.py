from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.auth_views import RolViewSet, UsuarioViewSet, RegistroConInvitacionView
from .views.bodega_views import BodegaViewSet
from .views.trabajador_views import TrabajadorViewSet
from .views.inventario_views import InventarioViewSet
from .views.dashboard_views import AlertaViewSet, DashboardResumenView, MLAnalyticsView, MLBusquedaView
from .views.movimiento_views import MovimientoInventarioViewSet
from .views.entrega_views import EntregaEPPViewSet, DetalleEntregaEPPViewSet
from .views.unidad_activo_views import UnidadActivoViewSet
from .views.auth_views import MeView
from .views.password_views import PasswordResetRequestView, PasswordResetConfirmView
from .views.auditoria_views import AuditoriaInventarioViewSet
from .views.despacho_rapido_views import DespachoRapidoView, DespachoRapidoStatsView

router = DefaultRouter()

router.register(r"roles", RolViewSet, basename="rol")
router.register(r"usuarios", UsuarioViewSet, basename="usuario")
router.register(r"trabajadores", TrabajadorViewSet, basename="trabajador")
router.register(r"inventario", InventarioViewSet, basename="inventario")
router.register(r"alertas", AlertaViewSet, basename="alerta")
router.register(r"bodegas", BodegaViewSet, basename="bodega")
router.register(r"movimientos", MovimientoInventarioViewSet, basename="movimiento")
router.register(r"entregas-epp", EntregaEPPViewSet, basename="entrega-epp")
router.register(r"detalles-entrega-epp", DetalleEntregaEPPViewSet, basename="detalle-entrega-epp")
router.register(r"unidades-activo", UnidadActivoViewSet, basename="unidad-activo")
router.register(r"auditorias-inventario", AuditoriaInventarioViewSet, basename="auditoria-inventario")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/resumen/", DashboardResumenView.as_view(), name="dashboard_resumen"),
    path("dashboard/ml-avanzado/", MLAnalyticsView.as_view(), name="dashboard_ml_avanzado"),
    path("dashboard/ml-busqueda/", MLBusquedaView.as_view(), name="dashboard_ml_busqueda"),
    path("despacho-rapido/", DespachoRapidoView.as_view(), name="despacho_rapido"),
    path("despacho-rapido/stats/", DespachoRapidoStatsView.as_view(), name="despacho_rapido_stats"),
    path("register/", RegistroConInvitacionView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("password-reset-confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"), 
]