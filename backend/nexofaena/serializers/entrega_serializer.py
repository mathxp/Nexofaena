from django.utils import timezone
from rest_framework import serializers

from nexofaena.models.entrega import EntregaEPP, DetalleEntregaEPP


class DetalleEntregaEPPSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="inventario.nombre", read_only=True)
    producto_codigo = serializers.CharField(source="inventario.codigo", read_only=True)
    es_devolutivo = serializers.BooleanField(source="inventario.es_devolutivo", read_only=True)
    unidad_activo_codigo = serializers.CharField(source="unidad_activo.codigo", read_only=True, default=None)
    trabajador_nombre = serializers.SerializerMethodField()
    trabajador_rut = serializers.CharField(source="entrega.trabajador.rut", read_only=True)
    bodega_nombre = serializers.CharField(source="entrega.bodega.nombre", read_only=True)
    dias_para_vencer = serializers.SerializerMethodField()

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
        ]
        read_only_fields = [
            "entrega", "fecha_vencimiento_vida_util", "devuelto",
            "fecha_devolucion", "estado_devolucion",
        ]

    def get_trabajador_nombre(self, obj):
        trabajador = obj.entrega.trabajador
        return f"{trabajador.nombres} {trabajador.apellido_paterno}"

    def get_dias_para_vencer(self, obj):
        if not obj.fecha_vencimiento_vida_util:
            return None

        return (obj.fecha_vencimiento_vida_util - timezone.now().date()).days


class EntregaEPPSerializer(serializers.ModelSerializer):
    detalles = DetalleEntregaEPPSerializer(many=True, read_only=True)

    trabajador_nombre = serializers.SerializerMethodField()
    trabajador_rut = serializers.CharField(source="trabajador.rut", read_only=True)
    usuario_nombre = serializers.CharField(source="usuario.username", read_only=True)
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)

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
            "detalles",
        ]

    def get_trabajador_nombre(self, obj):
        return f"{obj.trabajador.nombres} {obj.trabajador.apellido_paterno}"