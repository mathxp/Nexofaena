from django.contrib import admin

from .models import Rol
from .models import Trabajador
from .models import Usuario
from .models import UnidadActivo
from nexofaena.models.invitacion import InvitacionRegistro
admin.site.register(Rol)
admin.site.register(Trabajador)
admin.site.register(Usuario)


@admin.register(UnidadActivo)
class UnidadActivoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "inventario", "estado", "fecha_creacion"]
    list_filter = ["estado", "inventario__bodega"]
    search_fields = ["codigo", "inventario__nombre"]

@admin.register(InvitacionRegistro)
class InvitacionRegistroAdmin(admin.ModelAdmin):
    list_display = [
        "token",
        "correo",
        "usado",
        "fecha_creacion",
        "fecha_expiracion",
    ]
    list_filter = [
        "usado",
        "fecha_creacion",
    ]
    search_fields = [
        "correo",
        "token",
    ]
    readonly_fields = [
        "token",
        "fecha_creacion",
    ]