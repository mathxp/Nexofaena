from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importaciones previas...
from .views.auth_views import RolViewSet, UsuarioViewSet
from .views.trabajador_views import TrabajadorViewSet
from .views.inventario_views import BodegaViewSet, InventarioViewSet, MovimientoInventarioViewSet
from .views.epp_views import EPPViewSet, EntregaEPPViewSet, DetalleEntregaEPPViewSet

# Importaciones Sprint 5
from .views.dashboard_views import AlertaViewSet, DashboardResumenView 

router = DefaultRouter()

# Sprints 1, 2, 3, y 4 (Mantenemos todo lo que ya tenías)
router.register(r'roles', RolViewSet, basename='rol')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'trabajadores', TrabajadorViewSet, basename='trabajador')
router.register(r'bodegas', BodegaViewSet, basename='bodega')
router.register(r'inventario', InventarioViewSet, basename='inventario')
router.register(r'movimientos', MovimientoInventarioViewSet, basename='movimiento')
router.register(r'epps', EPPViewSet, basename='epp')
router.register(r'entregas-epp', EntregaEPPViewSet, basename='entrega_epp')
router.register(r'detalles-entrega', DetalleEntregaEPPViewSet, basename='detalle_entrega')

# Sprint 5: Alertas
router.register(r'alertas', AlertaViewSet, basename='alerta')

urlpatterns = [
    # Incluimos las rutas del router
    path('', include(router.urls)),
    
    # Ruta especial del Dashboard
    path('dashboard/resumen/', DashboardResumenView.as_view(), name='dashboard_resumen'),
]