from rest_framework import serializers

from nexofaena.models.auditoria_inventario import (
    AuditoriaInventario,
    DetalleAuditoriaInventario,
)


class DetalleAuditoriaSerializer(serializers.ModelSerializer):

    producto = serializers.CharField(
        source="inventario.nombre",
        read_only=True,
    )

    codigo = serializers.CharField(
        source="inventario.codigo",
        read_only=True,
    )

    class Meta:
        model = DetalleAuditoriaInventario
        fields = [
            "id",
            "inventario",
            "producto",
            "codigo",
            "stock_sistema",
            "stock_fisico",
            "diferencia",
            "observacion",
        ]


class AuditoriaSerializer(serializers.ModelSerializer):

    bodega_nombre = serializers.CharField(
        source="bodega.nombre",
        read_only=True,
    )

    usuario_nombre = serializers.CharField(
        source="usuario.username",
        read_only=True,
    )

    detalles = DetalleAuditoriaSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = AuditoriaInventario

        fields = [
            "id",
            "bodega",
            "bodega_nombre",
            "usuario",
            "usuario_nombre",
            "fecha_inicio",
            "fecha_cierre",
            "estado",
            "observacion",
            "detalles",
        ]