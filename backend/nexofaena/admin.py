from django.contrib import admin

from .models import Rol
from .models import Trabajador
from .models import Usuario
from nexofaena.models.invitacion import InvitacionRegistro
admin.site.register(Rol)
admin.site.register(Trabajador)
admin.site.register(Usuario)

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