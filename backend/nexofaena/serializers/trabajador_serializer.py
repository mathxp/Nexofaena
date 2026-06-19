from rest_framework import serializers
from nexofaena.models.trabajador import Trabajador

class TrabajadorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trabajador
        fields = '__all__'