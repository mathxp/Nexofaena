from rest_framework import serializers
from nexofaena.models.rol import Rol
from nexofaena.models.usuario import Usuario

class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = '__all__'

class UsuarioSerializer(serializers.ModelSerializer):
    # Opcional: Esto permite mostrar los datos del rol anidado en lugar de solo su ID
    # rol_detalle = RolSerializer(source='rol', read_only=True)

    class Meta:
        model = Usuario
        # Excluimos la contraseña por seguridad en las respuestas de la API
        fields = ['id', 'username', 'email', 'rut', 'telefono', 'rol', 'is_active']