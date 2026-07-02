from rest_framework import serializers
from nexofaena.models.rol import Rol
from nexofaena.models.usuario import Usuario
from nexofaena.models.invitacion import InvitacionRegistro


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = "__all__"


class UsuarioSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source="rol.nombre", read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "rut",
            "email",
            "first_name",
            "last_name",
            "rol",
            "telefono",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "rol_nombre",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        usuario = Usuario(**validated_data)

        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()

        usuario.save()
        return usuario


class RegistroConInvitacionSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    username = serializers.CharField()
    rut = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    telefono = serializers.CharField(required=False, allow_blank=True)
    rol = serializers.PrimaryKeyRelatedField(queryset=Rol.objects.all())

    def validate(self, data):
        token = data.get("token")

        try:
            invitacion = InvitacionRegistro.objects.get(token=token)
        except InvitacionRegistro.DoesNotExist:
            raise serializers.ValidationError("Token de invitación inválido.")

        if not invitacion.esta_vigente():
            raise serializers.ValidationError("Token de invitación vencido o ya utilizado.")

        if Usuario.objects.filter(username=data["username"]).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese username.")

        if Usuario.objects.filter(rut=data["rut"]).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese RUT.")

        data["invitacion"] = invitacion
        return data

    def create(self, validated_data):
        invitacion = validated_data.pop("invitacion")
        token = validated_data.pop("token")
        password = validated_data.pop("password")

        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()

        invitacion.usado = True
        invitacion.save(update_fields=["usado"])

        return usuario