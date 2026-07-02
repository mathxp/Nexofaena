from rest_framework import serializers
from nexofaena.models.trabajador import Trabajador


class TrabajadorSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)

    class Meta:
        model = Trabajador
        fields = [
            "id",
            "rut",
            "nombres",
            "apellido_paterno",
            "apellido_materno",
            "nombre_completo",
            "cargo",
            "telefono",
            "correo",
            "activo",
            "fecha_ingreso",
        ]
        read_only_fields = [
            "fecha_creacion",
            "fecha_actualizacion",
        ]

    def validate_rut(self, value: str) -> str:
        value = value.strip().upper()

        if len(value) < 8 or len(value) > 12:
            raise serializers.ValidationError("El formato del RUT no es válido.")

        queryset = Trabajador.objects.filter(rut=value)

        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("Ya existe un trabajador con este RUT.")

        return value

    def validate_nombres(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")

        return value

    def validate_apellido_paterno(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise serializers.ValidationError("El apellido paterno es obligatorio.")

        return value

    def validate_correo(self, value: str) -> str:
        value = value.strip() if value else ""

        if value and "@" not in value:
            raise serializers.ValidationError("Ingrese un correo electrónico válido.")

        return value