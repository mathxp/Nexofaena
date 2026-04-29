from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

# ======================
# VIEWS INVENTARIO
# ======================
from inventario.views import (
    dashboard,
    lista_insumos,
    crear_insumo,
    editar_insumo,
    eliminar_insumo,

    reporte_inventario,
    reporte_movimientos,
    analisis_consumo,
    generar_prediccion,

    exportar_excel,
    exportar_inventario_pdf,
    exportar_inventario_excel,

    crear_compra,
    historial_compras,
    agregar_detalle,
    crear_salida,

    dashboard_financiero,

    registro,
    home,
)

# ======================
# VIEWS USUARIOS
# ======================
from usuarios.views import (
    lista_usuarios,
    crear_usuario,
    editar_usuario,
    eliminar_usuario
)

# ======================
# VIEWS SOLICITUDES
# ======================
from solicitudes.views import (
    crear_solicitud,
    lista_solicitudes,
    cambiar_estado_solicitud
)

# ======================
# URLS
# ======================
urlpatterns = [

    # ======================
    # ADMIN
    # ======================
    path('admin/', admin.site.urls),

    # ======================
    # HOME / DASHBOARD
    # ======================
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('dashboard-financiero/', dashboard_financiero, name='dashboard_financiero'),

    # ======================
    # AUTENTICACIÓN
    # ======================
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', registro, name='registro'),

    # ======================
    # INVENTARIO
    # ======================
    path('insumos/', lista_insumos, name='lista_insumos'),
    path('insumos/crear/', crear_insumo, name='crear_insumo'),
    path('insumos/editar/<int:id>/', editar_insumo, name='editar_insumo'),
    path('insumos/eliminar/<int:id>/', eliminar_insumo, name='eliminar_insumo'),

    # ======================
    # REPORTES
    # ======================
    path('reportes/inventario/', reporte_inventario, name='reporte_inventario'),
    path('reportes/movimientos/', reporte_movimientos, name='reporte_movimientos'),
    path('reportes/consumo/', analisis_consumo, name='analisis_consumo'),
    path('reportes/prediccion/', generar_prediccion, name='prediccion'),

    # EXPORTACIONES
    path('reportes/inventario/excel/', exportar_inventario_excel, name='exportar_inventario_excel'),
    path('reportes/inventario/pdf/', exportar_inventario_pdf, name='exportar_inventario_pdf'),
    path('exportar-excel/', exportar_excel, name='exportar_excel'),

    # ======================
    # USUARIOS
    # ======================
    path('usuarios/', lista_usuarios, name='lista_usuarios'),
    path('usuarios/crear/', crear_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:id>/', editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:id>/', eliminar_usuario, name='eliminar_usuario'),

    # ======================
    # COMPRAS
    # ======================
    path('compras/', historial_compras, name='historial_compras'),
    path('compras/crear/', crear_compra, name='crear_compra'),
    path('compras/<int:compra_id>/detalle/', agregar_detalle, name='agregar_detalle'),

    # SALIDAS
    path('salidas/crear/', crear_salida, name='crear_salida'),

    # ======================
    # SOLICITUDES
    # ======================
    path('solicitudes/', lista_solicitudes, name='lista_solicitudes'),
    path('solicitudes/crear/', crear_solicitud, name='crear_solicitud'),
    path('solicitudes/<int:id>/<str:estado>/', cambiar_estado_solicitud, name='cambiar_estado_solicitud'),
]

# ======================
# STATIC FILES (DESARROLLO)
# ======================
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])