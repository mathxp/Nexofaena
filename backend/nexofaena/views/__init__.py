# views/__init__.py
from .auth_views import RolViewSet, UsuarioViewSet
from .trabajador_views import TrabajadorViewSet
from .inventario_views import BodegaViewSet, InventarioViewSet, MovimientoInventarioViewSet
from .epp_views import EPPViewSet, EntregaEPPViewSet, DetalleEntregaEPPViewSet
from .dashboard_views import DashboardViewSet
# ... tus otras importaciones ...