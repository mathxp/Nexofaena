from rest_framework import viewsets
from nexofaena.models.rol import Rol
from nexofaena.models.usuario import Usuario
from nexofaena.serializers.auth_serializer import RolSerializer, UsuarioSerializer

class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer