from rest_framework import serializers

from nexofaena.models.movimiento_inventario import MovimientoInventario


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)
    producto_nombre = serializers.CharField(source="inventario.nombre", read_only=True)
    trabajador_nombre = serializers.SerializerMethodField()
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoInventario
        fields = [
            "id",
            "tipo_movimiento",
            "cantidad",
            "stock_anterior",
            "stock_actual",
            "observacion",
            "fecha",
            "bodega",
            "bodega_nombre",
            "inventario",
            "producto_nombre",
            "trabajador",
            "trabajador_nombre",
            "usuario",
            "usuario_nombre",
        ]

    def get_trabajador_nombre(self, obj):
        if not obj.trabajador:
            return None
        return f"{obj.trabajador.nombres} {obj.trabajador.apellido_paterno}"

    def get_usuario_nombre(self, obj):
        if not obj.usuario:
            return None
        return obj.usuario.username