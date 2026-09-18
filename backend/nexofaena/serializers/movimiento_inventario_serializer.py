from rest_framework import serializers

from nexofaena.models.movimiento_inventario import MovimientoInventario


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)
    producto_nombre = serializers.CharField(source="inventario.nombre", read_only=True)
    bodega_destino_nombre = serializers.CharField(source="bodega_destino.nombre", read_only=True, default=None)
    producto_destino_nombre = serializers.CharField(source="inventario_destino.nombre", read_only=True, default=None)
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
            "bodega_destino",
            "bodega_destino_nombre",
            "inventario_destino",
            "producto_destino_nombre",
            "stock_anterior_destino",
            "stock_actual_destino",
            "trabajador",
            "trabajador_nombre",
            "usuario",
            "usuario_nombre",
        ]
        # El registro es inmutable (ver MovimientoInventarioViewSet.update):
        # ningún campo se edita después de creado. Se declara aquí también
        # como defensa en profundidad, en caso de que el serializer se use
        # alguna vez fuera de ese ViewSet.
        read_only_fields = [
            "tipo_movimiento", "cantidad", "stock_anterior", "stock_actual",
            "fecha", "bodega", "inventario", "trabajador", "usuario",
            "bodega_destino", "inventario_destino", "stock_anterior_destino", "stock_actual_destino",
        ]

    def get_trabajador_nombre(self, obj):
        if not obj.trabajador:
            return None
        return f"{obj.trabajador.nombres} {obj.trabajador.apellido_paterno}"

    def get_usuario_nombre(self, obj):
        if not obj.usuario:
            return None
        return obj.usuario.username