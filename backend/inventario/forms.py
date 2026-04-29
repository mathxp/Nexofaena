from django import forms
from .models import Insumo, Consumo

# ======================
# FORMULARIO INSUMO
# ======================
class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = '__all__'  # Incluye todos los campos del modelo


# ======================
# FORMULARIO CONSUMO
# ======================
class ConsumoForm(forms.ModelForm):
    class Meta:
        model = Consumo
        fields = ['insumo', 'cantidad', 'fecha']  # Campos específicos