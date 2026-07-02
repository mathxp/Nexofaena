from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from nexofaena.models.rol import Rol
from nexofaena.models.usuario import Usuario
from nexofaena.serializers.auth_serializer import (
    RolSerializer,
    UsuarioSerializer,
    RegistroConInvitacionSerializer,
)


class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer
    permission_classes = [IsAuthenticated]


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]


class RegistroConInvitacionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroConInvitacionSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response(
                {
                    "success": True,
                    "message": "Usuario registrado correctamente.",
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)