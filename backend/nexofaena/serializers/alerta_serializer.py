from rest_framework import serializers
from nexofaena.models.alerta import Alerta, TipoAlerta


class AlertaSerializer(serializers.ModelSerializer):
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)
    inventario_nombre = serializers.CharField(source="inventario.nombre", read_only=True)
    inventario_codigo = serializers.CharField(source="inventario.codigo", read_only=True)

    class Meta:
        model = Alerta
        fields = [
            "id",
            "tipo_alerta",
            "mensaje",
            "fecha_alerta",
            "leida",
            "bodega",
            "bodega_nombre",
            "inventario",
            "inventario_nombre",
            "inventario_codigo",
        ]
        read_only_fields = ["fecha_alerta"]

    def validate_tipo_alerta(self, value):
        tipos_validos = [choice[0] for choice in TipoAlerta.choices]

        if value not in tipos_validos:
            raise serializers.ValidationError("Tipo de alerta inválido.")

        return value