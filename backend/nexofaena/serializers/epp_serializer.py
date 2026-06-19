from rest_framework import serializers
from nexofaena.models.epp import EPP
from nexofaena.models.entrega_epp import EntregaEPP, DetalleEntregaEPP

class EPPSerializer(serializers.ModelSerializer):
    class Meta:
        model = EPP
        fields = '__all__'

class DetalleEntregaEPPSerializer(serializers.ModelSerializer):
    # Esto es opcional, pero útil: mostrar el nombre del EPP en vez de solo su ID
    nombre_epp = serializers.CharField(source='epp.nombre', read_only=True)

    class Meta:
        model = DetalleEntregaEPP
        fields = ['id','entrega', 'epp', 'nombre_epp', 'cantidad', 'talla', 'observacion']

class EntregaEPPSerializer(serializers.ModelSerializer):
    # Anidamos los detalles para que al pedir una Entrega, nos traiga la lista de lo que se entregó
    detalles = DetalleEntregaEPPSerializer(many=True, read_only=True)
    nombre_trabajador = serializers.CharField(source='trabajador.rut', read_only=True)

    class Meta:
        model = EntregaEPP
        fields = [
            'id', 'trabajador', 'nombre_trabajador', 'usuario', 
            'fecha_entrega', 'observacion', 'firma_base64', 'estado', 'detalles'
        ]