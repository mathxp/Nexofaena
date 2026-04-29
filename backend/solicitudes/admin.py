from django.contrib import admin
from .models import Solicitud, DetalleSolicitud

class DetalleInline(admin.TabularInline):
    model = DetalleSolicitud
    extra = 1

@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ('id', 'area', 'usuario', 'estado', 'fecha')
    list_filter = ('estado', 'area')
    inlines = [DetalleInline]