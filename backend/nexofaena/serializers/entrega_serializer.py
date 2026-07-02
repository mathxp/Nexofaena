from rest_framework import serializers

from nexofaena.models.entrega import EntregaEPP, DetalleEntregaEPP


class DetalleEntregaEPPSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="inventario.nombre", read_only=True)
    producto_codigo = serializers.CharField(source="inventario.codigo", read_only=True)

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
        ]
        read_only_fields = ["entrega"]


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