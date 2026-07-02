from rest_framework import serializers
from nexofaena.models.bodega import Bodega


class BodegaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bodega
        fields = [
            "id",
            "nombre",
            "ubicacion",
            "responsable",
            "estado",
        ]

    def validate_nombre(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("El nombre de la bodega es obligatorio.")

        qs = Bodega.objects.filter(nombre__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Ya existe una bodega con este nombre.")

        return value