from rest_framework import serializers
from nexofaena.models.alerta import Alerta

class AlertaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alerta
        fields = '__all__'