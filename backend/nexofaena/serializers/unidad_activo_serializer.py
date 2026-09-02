from rest_framework import serializers

from nexofaena.models.unidad_activo import UnidadActivo


class UnidadActivoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="inventario.nombre", read_only=True)
    bodega = serializers.IntegerField(source="inventario.bodega_id", read_only=True)
    bodega_nombre = serializers.CharField(source="inventario.bodega.nombre", read_only=True)

    class Meta:
        model = UnidadActivo
        fields = [
            "id",
            "inventario",
            "producto_nombre",
            "bodega",
            "bodega_nombre",
            "codigo",
            "estado",
            "fecha_creacion",
        ]
        read_only_fields = ["estado", "fecha_creacion"]
