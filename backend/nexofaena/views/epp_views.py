from rest_framework import viewsets
from nexofaena.models.epp import EPP
from nexofaena.models.entrega_epp import EntregaEPP, DetalleEntregaEPP

from nexofaena.serializers.epp_serializer import (
    EPPSerializer, 
    EntregaEPPSerializer, 
    DetalleEntregaEPPSerializer
)

class EPPViewSet(viewsets.ModelViewSet):
    queryset = EPP.objects.all()
    serializer_class = EPPSerializer

class EntregaEPPViewSet(viewsets.ModelViewSet):
    queryset = EntregaEPP.objects.all()
    serializer_class = EntregaEPPSerializer

class DetalleEntregaEPPViewSet(viewsets.ModelViewSet):
    queryset = DetalleEntregaEPP.objects.all()
    serializer_class = DetalleEntregaEPPSerializer