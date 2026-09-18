from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from nexofaena.models.entrega import EntregaEPP, DetalleEntregaEPP
from nexofaena.services.reporte_service import ReporteService

# Roles con necesidad operativa real de ver el RUT completo (identificar al
# trabajador en el pañol). El resto (ej. Supervisor revisando reportes) recibe
# el RUT enmascarado, igual que en el reporte de consumo por turno.
ROLES_CON_RUT_COMPLETO = ("Administrador", "Bodeguero")


def _rut_segun_rol(request, rut):
    rol = getattr(getattr(request, "user", None), "rol", None)
    if rol and rol.nombre in ROLES_CON_RUT_COMPLETO:
        return rut
    return ReporteService.mascarar_rut(rut)


class DetalleEntregaEPPSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="inventario.nombre", read_only=True)
    producto_codigo = serializers.CharField(source="inventario.codigo", read_only=True)
    es_devolutivo = serializers.BooleanField(source="inventario.es_devolutivo", read_only=True)
    unidad_activo_codigo = serializers.CharField(source="unidad_activo.codigo", read_only=True, default=None)
    trabajador_nombre = serializers.SerializerMethodField()
    trabajador_rut = serializers.SerializerMethodField()
    bodega_nombre = serializers.CharField(source="entrega.bodega.nombre", read_only=True)
    dias_para_vencer = serializers.SerializerMethodField()
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = DetalleEntregaEPP
        fields = [
            "id",
            "entrega",
            "inventario",
            "producto_nombre",
            "producto_codigo",
            "cantidad",
            "talla",
            "observacion",
            "fecha_vencimiento_vida_util",
            "dias_para_vencer",
            "es_devolutivo",
            "unidad_activo",
            "unidad_activo_codigo",
            "devuelto",
            "fecha_devolucion",
            "estado_devolucion",
            "trabajador_nombre",
            "trabajador_rut",
            "bodega_nombre",
            "precio_unitario",
            "subtotal",
        ]
        read_only_fields = [
            "entrega", "fecha_vencimiento_vida_util", "devuelto",
            "fecha_devolucion", "estado_devolucion", "precio_unitario",
        ]

    def get_trabajador_nombre(self, obj):
        trabajador = obj.entrega.trabajador
        return f"{trabajador.nombres} {trabajador.apellido_paterno}"

    def get_trabajador_rut(self, obj):
        return _rut_segun_rol(self.context.get("request"), obj.entrega.trabajador.rut)

    def get_dias_para_vencer(self, obj):
        if not obj.fecha_vencimiento_vida_util:
            return None

        return (obj.fecha_vencimiento_vida_util - timezone.now().date()).days


class EntregaEPPSerializer(serializers.ModelSerializer):
    detalles = DetalleEntregaEPPSerializer(many=True, read_only=True)

    trabajador_nombre = serializers.SerializerMethodField()
    trabajador_rut = serializers.SerializerMethodField()
    usuario_nombre = serializers.CharField(source="usuario.username", read_only=True)
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)
    valor_total = serializers.SerializerMethodField()

    class Meta:
        model = EntregaEPP
        fields = [
            "id",
            "trabajador",
            "trabajador_nombre",
            "trabajador_rut",
            "usuario",
            "usuario_nombre",
            "bodega",
            "bodega_nombre",
            "fecha_entrega",
            "observacion",
            "firma_base64",
            "estado",
            "latitud",
            "longitud",
            "precision_metros",
            "geolocalizacion_capturada_en",
            "detalles",
            "valor_total",
        ]

    def get_trabajador_nombre(self, obj):
        return f"{obj.trabajador.nombres} {obj.trabajador.apellido_paterno}"

    def get_trabajador_rut(self, obj):
        return _rut_segun_rol(self.context.get("request"), obj.trabajador.rut)

    def get_valor_total(self, obj):
        return sum((detalle.subtotal for detalle in obj.detalles.all()), Decimal('0'))