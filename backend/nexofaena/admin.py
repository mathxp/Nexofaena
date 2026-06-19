from django.contrib import admin

from .models import Rol
from .models import Trabajador
from .models import Usuario

admin.site.register(Rol)
admin.site.register(Trabajador)
admin.site.register(Usuario)