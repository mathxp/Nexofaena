from rest_framework import viewsets
from nexofaena.models.trabajador import Trabajador
from nexofaena.serializers.trabajador_serializer import TrabajadorSerializer

class TrabajadorViewSet(viewsets.ModelViewSet):
    queryset = Trabajador.objects.all()
    serializer_class = TrabajadorSerializer