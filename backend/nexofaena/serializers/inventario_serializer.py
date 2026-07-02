from rest_framework import serializers
from nexofaena.models.inventario import Inventario


class InventarioSerializer(serializers.ModelSerializer):
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)
    necesita_reposicion = serializers.BooleanField(read_only=True)
    exceso_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventario
        fields = [
            "id", "bodega", "bodega_nombre", "codigo", "nombre",
            "descripcion", "marca", "modelo", "unidad_medida",
            "stock_actual", "stock_minimo", "stock_maximo",
            "ubicacion", "estado", "necesita_reposicion", "exceso_stock",
        ]
        read_only_fields = ["fecha_creacion", "fecha_actualizacion"]

    def validate_codigo(self, value):
        value = value.strip().upper()

        if not value:
            raise serializers.ValidationError("El código es obligatorio.")

        bodega = self.initial_data.get("bodega") if hasattr(self, "initial_data") else None

        if bodega:
            qs = Inventario.objects.filter(codigo=value, bodega_id=bodega)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise serializers.ValidationError(
                    "Ya existe un producto con este código en la bodega seleccionada."
                )

        return value

    def validate_nombre(self, value):
        if not value.strip():
            raise serializers.ValidationError("El nombre del producto es obligatorio.")
        return value.strip()

    def validate(self, data):
        stock_actual = data.get("stock_actual", getattr(self.instance, "stock_actual", 0))
        stock_minimo = data.get("stock_minimo", getattr(self.instance, "stock_minimo", 0))
        stock_maximo = data.get("stock_maximo", getattr(self.instance, "stock_maximo", 0))

        if stock_actual < 0:
            raise serializers.ValidationError({"stock_actual": "El stock actual no puede ser negativo."})

        if stock_minimo < 0:
            raise serializers.ValidationError({"stock_minimo": "El stock mínimo no puede ser negativo."})

        if stock_maximo < 0:
            raise serializers.ValidationError({"stock_maximo": "El stock máximo no puede ser negativo."})

        if stock_maximo > 0 and stock_minimo > stock_maximo:
            raise serializers.ValidationError(
                {"stock_minimo": "El stock mínimo no puede ser mayor al stock máximo."}
            )

        if stock_maximo > 0 and stock_actual > stock_maximo:
            raise serializers.ValidationError(
                {"stock_actual": "El stock actual no puede superar el stock máximo."}
            )

        return data